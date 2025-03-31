import os
import yaml
import torch
import argparse
import easydict
import torchvision
import numpy as np
from tqdm import tqdm
from utils.image_utils import read_image, save_image
from gaussian_renderer import render
from scene.cameras import get_render_camera
from scene.gaussian_model import GaussianModel
from scene.scene_loader import Scene, SceneDataset
from scene.colmap_loader import read_colmap_views_info


def color_correct(img: np.ndarray, ref: np.ndarray, num_iters: int = 5, eps: float = 0.5 / 255):
    """Warp `img` to match the colors in `ref_img`."""
    if img.shape[-1] != ref.shape[-1]:
        raise ValueError(
            f'img\'s {img.shape[-1]} and ref\'s {ref.shape[-1]} channels must match'
        )
    num_channels = img.shape[-1]
    img_mat = img.reshape([-1, num_channels])
    ref_mat = ref.reshape([-1, num_channels])
    is_unclipped = lambda z: (z >= eps) & (z <= (1 - eps))  # z \in [eps, 1-eps].
    mask0 = is_unclipped(img_mat)

    # Because the set of saturated pixels may change after solving for a
    # transformation, we repeatedly solve a system `num_iters` times and update
    # our estimate of which pixels are saturated.
    for _ in range(num_iters):
        # Construct the left hand side of a linear system that contains a quadratic
        # expansion of each pixel of `img`.
        a_mat = []
        for c in range(num_channels):
            a_mat.append(img_mat[:, c:(c + 1)] * img_mat[:, c:])  # Quadratic term.
        a_mat.append(img_mat)  # Linear term.
        a_mat.append(np.ones_like(img_mat[:, :1]))  # Bias term.
        a_mat = np.concatenate(a_mat, axis=-1)
        warp = []
        for c in range(num_channels):
            # Construct the right hand side of a linear system containing each color
            # of `ref`.
            b = ref_mat[:, c]
            # Ignore rows of the linear system that were saturated in the input or are
            # saturated in the current corrected color estimate.
            mask = mask0[:, c] & is_unclipped(img_mat[:, c]) & is_unclipped(b)
            ma_mat = np.where(mask[:, None], a_mat, 0)
            mb = np.where(mask, b, 0) # pylint: disable=C0103
            # Solve the linear system. We're using the np.lstsq instead of np because
            # it's significantly more stable in this case, for some reason.
            w = np.linalg.lstsq(ma_mat, mb, rcond=-1)[0]
            assert np.all(np.isfinite(w))
            warp.append(w)
        warp = np.stack(warp, axis=-1)
        # Apply the warp to update img_mat.
        img_mat = np.clip(np.matmul(a_mat, warp), 0, 1)
    corrected_img = np.reshape(img_mat, img.shape)

    return corrected_img


def render_views(cfg, scene_gaussian, image_rendered_dirpath, views_info_list, color_correction=False):
    os.makedirs(image_rendered_dirpath, exist_ok=True)
    device = torch.device("cuda")
    bg_color = [1, 1, 1] if cfg.white_background else [0, 0, 0]
    background = torch.tensor(bg_color, dtype=torch.float32, device=device)
    bg = torch.rand((3), device=device) if cfg.random_background else background
    dataset = SceneDataset(views_info_list, cfg.image_scale, cfg.scene_scale)
    dataloader = torch.utils.data.DataLoader(dataset, batch_size=1, shuffle=False, num_workers=4, drop_last=False)

    for idx, view_info in enumerate(tqdm(dataloader, desc="Rendering")):
        extrinsic = view_info["extrinsic"].squeeze(0).to(device)
        intrinsic = view_info["intrinsic"].squeeze(0).to(device)
        image_height, image_width = view_info["image_height"].item(), view_info["image_width"].item()
        camera_render = get_render_camera(image_height, image_width, extrinsic, intrinsic)
        render_pkg = render(camera_render, scene_gaussian, cfg, bg)
        image_rendered = torch.clamp(render_pkg["render"], 0.0, 1.0)   # [3, H, W]

        image_rendered = image_rendered.permute(1, 2, 0).cpu().numpy()
        # color_correct
        if color_correction:
            image_ref = read_image(view_info["image_filepath"][0], image_scale=cfg.image_scale)
            image_rendered = color_correct(image_rendered, image_ref)

        image_name = os.path.basename(view_info["image_filepath"][0]).replace("jpg", "png").replace("JPG", "png")
        save_image(image_rendered, os.path.join(image_rendered_dirpath, image_name))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Metrics calculation script parameters.")
    parser.add_argument("--optimized_path", "-o", type=str, default="./output/rubble", help="optimized scene dirpath")
    parser.add_argument("--train_eval_split", action="store_true", help="train and eval is stored sperately")
    parser.add_argument("--eval_only", action="store_true", help="donot cal metrics on train-views")
    args = parser.parse_args()

    config_filepath = os.path.join(args.optimized_path, "config.yaml")
    with open(config_filepath, "rb") as f:
        cfg = yaml.load(f, Loader=yaml.FullLoader)
    cfg = easydict.EasyDict(cfg)
    cfg.output_dirpath = args.optimized_path

    with torch.no_grad():
        scene_gaussian = GaussianModel(sh_degree=cfg.sh_degree)
        postfix_pcd_dirpath = os.path.join(cfg.output_dirpath, "point_cloud_postfix")
        pcd_plypath = os.path.join(cfg.output_dirpath, "point_cloud_merged.ply")
        if os.path.exists(pcd_plypath):
            scene_gaussian.load_ply(pcd_plypath)
        elif os.path.exists(postfix_pcd_dirpath):
            assert os.path.exists(postfix_pcd_dirpath), "{} does not exist.".format(postfix_pcd_dirpath)
            scene_gaussian.load_blocks_ply(postfix_pcd_dirpath)
        else:
            raise ValueError("Both postfix_pcd_dirpath and merged_pcd_plypath do not exist.")
        print("Num Gaussian points:", scene_gaussian.get_xyz.shape[0])

        if args.train_eval_split:
            eval_views_info, _, __ = read_colmap_views_info(cfg.scene_dirpath.replace("train", "val"), evaluate=False, scene_scale=cfg.scene_scale)
            eval_views_info_list = list(eval_views_info.values())
            eval_rendered_dirpath = os.path.join(cfg.output_dirpath, "render", "eval", "rendered")
            render_views(cfg, scene_gaussian, eval_rendered_dirpath, eval_views_info_list, color_correction=True)
            if not args.eval_only:
                scene_train = Scene(cfg.scene_dirpath, evaluate=cfg.evaluate, scene_scale=cfg.scene_scale)
                train_views_info_list = list(scene_train.views_info.values())
                train_rendered_dirpath = os.path.join(cfg.output_dirpath, "render", "train", "rendered")
                render_views(cfg, scene_gaussian, train_rendered_dirpath, train_views_info_list)
        else:
            scene = Scene(cfg.scene_dirpath, evaluate=cfg.evaluate, scene_scale=cfg.scene_scale)
            eval_views_info_list = [scene.views_info[view_id] for view_id in scene.eval_views_id]
            eval_rendered_dirpath = os.path.join(cfg.output_dirpath, "render", "eval", "rendered")
            render_views(cfg, scene_gaussian, eval_rendered_dirpath, eval_views_info_list, color_correction=True)
            if not args.eval_only:
                train_views_info_list = [scene.views_info[view_id] for view_id in scene.train_views_id]
                train_rendered_dirpath = os.path.join(cfg.output_dirpath, "render", "train", "rendered")
                render_views(cfg, scene_gaussian, train_rendered_dirpath, train_views_info_list)
