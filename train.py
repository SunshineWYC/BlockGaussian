import os
import cv2
import json
import time
import torch
import shutil
import random
import argparse
import numpy as np
from tqdm import tqdm
from gaussian_renderer import render
from utils.image_utils import psnr
from utils.general_utils import get_expon_lr_func
from utils.loss_utils import l1_loss, ssim, src2ref, loss_reproj
from scene.cameras import get_render_camera
from scene.gaussian_model import GaussianModel
from scene.scene_loader import SceneDataset, Scene
from utils.utils import parse_cfg, cal_local_cam_extent, save_cfg, read_pcdfile, visual_image_rendered
from torch.utils.tensorboard import SummaryWriter
try:
    from fused_ssim import fused_ssim
    FUSED_SSIM_AVAILABLE = True
except:
    FUSED_SSIM_AVAILABLE = False


seed = 42
random.seed(seed)
np.random.seed(seed)
torch.manual_seed(seed)
torch.cuda.manual_seed(seed)
torch.cuda.manual_seed_all(seed)


def reconstruct(cfg, block_id, block_bbx_expand, views_info_list, init_pcd, eval_views_info=None, device=torch.device("cuda")):
    block_bbx = block_bbx_expand
    # tb_writer = SummaryWriter(cfg.output_dirpath)  # tensorboard writer
    tb_writer = None
    print("Reconstructing block {}, ".format(block_id), "Num block views: ", len(views_info_list))
    point_cloud_path = os.path.join(cfg.output_dirpath, "point_cloud")
    # local gaussian definition
    local_gaussian = GaussianModel(sh_degree=cfg.sh_degree)
    bg_color = [1, 1, 1] if cfg.white_background else [0, 0, 0]
    background = torch.tensor(bg_color, dtype=torch.float32, device=device)
    bg = torch.rand((3), device=device) if cfg.random_background else background

    # setting block optimization hyper params
    num_views = len(views_info_list)
    # cfg.iterations = min(num_views*150, cfg.iterations)
    cfg.position_lr_max_steps = cfg.iterations
    cfg.densify_until_iter = cfg.iterations // 2
    cfg.opacity_reset_interval = max(cfg.iterations//10, 3000)
    save_cfg(cfg, block_id)

    # scene_dataset defination
    scene_dataset = SceneDataset(views_info_list, cfg.image_scale, cfg.scene_scale, cfg.iterations*cfg.batch_size, preload=cfg.preload)
    scene_dataloader = torch.utils.data.DataLoader(scene_dataset, batch_size=cfg.batch_size, shuffle=True, num_workers=cfg.num_workers, drop_last=False, pin_memory=True)
    if eval_views_info is not None:
        eval_dataset = SceneDataset(eval_views_info, cfg.image_scale, cfg.scene_scale)
        eval_dataloader = torch.utils.data.DataLoader(eval_dataset, batch_size=1, shuffle=False, num_workers=cfg.num_workers, drop_last=False)

    # initialize local gaussian
    scene_extent = cal_local_cam_extent(views_info_list)  # calculate local_gaussian extent
    print("Scene extent: ", scene_extent)
    local_gaussian.create_from_pcd(init_pcd, scene_extent)
    local_gaussian.training_setup(cfg)

    depth_l1_weight = get_expon_lr_func(cfg.depth_l1_weight_init, cfg.depth_l1_weight_final, max_steps=cfg.iterations)
    reproj_l1_weight = get_expon_lr_func(cfg.reproj_l1_weight_init, cfg.reproj_l1_weight_final, max_steps=cfg.iterations)

    start_time = time.time()
    # optimizaiton process
    for iter_idx, view_info in enumerate(tqdm(scene_dataloader, desc="Reconstructing:{}".format(block_id))):
        iteration = iter_idx + 1
        local_gaussian.update_learning_rate(iteration)
        if iteration % 1000 == 0: local_gaussian.oneupSHdegree()
        batch_sample_num = view_info["extrinsic"].shape[0]

        # render image and accumulate loss grad among batch
        for sample_idx in range(0, batch_sample_num):
            extrinsic = view_info["extrinsic"][sample_idx].to(device)
            intrinsic = view_info["intrinsic"][sample_idx].to(device)
            image_height, image_width = view_info["image_height"][sample_idx].item(), view_info["image_width"][sample_idx].item()
            image_gt = view_info["image"][sample_idx].to(device)
            camera_render = get_render_camera(image_height, image_width, extrinsic, intrinsic)
            render_pkg = render(camera_render, local_gaussian, cfg, bg)
            image_rendered = render_pkg["render"]   # [3, H, W]

            # calculate photo loss
            l1_loss_photo = l1_loss(image_rendered, image_gt)
            if FUSED_SSIM_AVAILABLE:
                ssim_value = fused_ssim(image_rendered.unsqueeze(0), image_gt.unsqueeze(0))
            else:
                ssim_value = ssim(image_rendered, image_gt)
            loss_photo = (1.0 - cfg.lambda_dssim) * l1_loss_photo + cfg.lambda_dssim * (1.0 - ssim_value)

            loss_scaling = local_gaussian.get_scaling.prod(dim=1).mean()
            loss = loss_photo + 0.01*loss_scaling

            # calculate depth loss
            if cfg.depth_inv_loss and not isinstance(view_info["depth_inv"][sample_idx], str):
                depth_rendered_inv = render_pkg["depth"].squeeze(0)
                depth_gt_inv = view_info["depth_inv"][sample_idx].to(device)
                l1_loss_depth = torch.abs(depth_gt_inv - depth_rendered_inv).mean()
                loss += depth_l1_weight(iteration) * l1_loss_depth

            # generate and render dummy view
            if cfg.pesudo_loss and iteration > cfg.pesudo_loss_start:
                depth_rendered = (1.0 / (render_pkg["depth"]+1e-8)).squeeze(0)  # [H, W]
                disturb = torch.tensor((0.05 * image_width * torch.median(depth_rendered) / intrinsic[0, 0], 0.0, 0.0), device=device)
                dummy_camera = get_render_camera(image_height, image_width, extrinsic, intrinsic, disturb=disturb)
                dummy_render_pkg = render(dummy_camera, local_gaussian, cfg, bg)
                dummy_rendered = torch.clamp(dummy_render_pkg["render"], 0.0, 1.0)
                dummy_depth_rendered = (1.0 / (dummy_render_pkg["depth"]+1e-8)).squeeze(0)  # [H, W]
                reprojected_depth, reprojected_image = src2ref(camera_render.intrinsic, camera_render.extrinsic, depth_rendered,
                                                            dummy_camera.intrinsic, dummy_camera.extrinsic, dummy_depth_rendered, dummy_rendered)
                loss_reproj_photo = loss_reproj(reprojected_depth, reprojected_image, image_gt)
                loss += reproj_l1_weight(iteration) * loss_reproj_photo
            loss.backward()

        with torch.no_grad():
            # Densification and Prune
            viewspace_point_tensor, visibility_filter, radii = render_pkg["viewspace_points"], render_pkg["visibility_filter"], render_pkg["radii"]
            if iteration < cfg.densify_until_iter:
                # Keep track of max radii in image-space for pruning
                local_gaussian.max_radii2D[visibility_filter] = torch.max(local_gaussian.max_radii2D[visibility_filter], radii[visibility_filter])
                local_gaussian.add_densification_stats(viewspace_point_tensor, visibility_filter)
                if iteration > cfg.densify_from_iter and iteration % cfg.densification_interval == 0:
                    size_threshold = 500 if iteration > cfg.opacity_reset_interval else None
                    block_bbx_ = block_bbx if cfg.densify_only_in_block else None
                    local_gaussian.densify_and_prune(cfg.densify_grad_threshold, cfg.min_opacity, scene_extent, size_threshold, block_bbx_)
                if iteration % cfg.opacity_reset_interval == 0 and iteration > cfg.densify_from_iter:
                    local_gaussian.reset_opacity()

            # Optimizer step
            local_gaussian.optimizer.step()
            local_gaussian.optimizer.zero_grad(set_to_none=True)

            # logger writer
            if tb_writer:
                tb_writer.add_scalar("block_{}/loss".format(block_id), loss.item(), iteration)
                tb_writer.add_scalar("block_{}/Npts".format(block_id), local_gaussian.get_xyz.shape[0], iteration)
                if cfg.depth_inv_loss and not isinstance(view_info["depth_inv"][sample_idx], str): 
                    tb_writer.add_scalar("block_{}/loss_depth".format(block_id), l1_loss_depth.item(), iteration)
                if cfg.pesudo_loss and iteration > cfg.pesudo_loss_start: 
                    tb_writer.add_scalar("block_{}/loss_reproj_photo".format(block_id), loss_reproj_photo.item(), iteration)
            # evaluate PNSR on train and eval view
            if iteration % 2000 == 0:
                psnr_train_acc = 0.0
                for idx, view_info in enumerate(scene_dataloader):
                    if idx >= 5: break
                    batch_sample_num = view_info["extrinsic"].shape[0]
                    for sample_idx in range(0, batch_sample_num):
                        extrinsic = view_info["extrinsic"][sample_idx].to(device)
                        intrinsic = view_info["intrinsic"][sample_idx].to(device)
                        image_height, image_width = view_info["image_height"][sample_idx].item(), view_info["image_width"][sample_idx].item()
                        image_gt = view_info["image"][sample_idx].to(device)
                        camera_render = get_render_camera(image_height, image_width, extrinsic, intrinsic)
                        render_pkg = render(camera_render, local_gaussian, cfg, bg)
                        image_rendered = render_pkg["render"]   # [3, H, W]
                        psnr_train_acc += psnr(image_rendered, image_gt).mean()
                if tb_writer: tb_writer.add_scalar("block_{}/train-PSNR".format(block_id), psnr_train_acc/5/cfg.batch_size, iteration)

                if eval_views_info is not None:
                    psnr_eval_acc = 0.0
                    for idx, view_info in enumerate(eval_dataloader):
                        extrinsic = view_info["extrinsic"].squeeze(0).to(device)
                        intrinsic = view_info["intrinsic"].squeeze(0).to(device)
                        image_height, image_width = view_info["image_height"].item(), view_info["image_width"].item()
                        image_gt = view_info["image"].squeeze(0).to(device)
                        camera_render = get_render_camera(image_height, image_width, extrinsic, intrinsic)
                        render_pkg = render(camera_render, local_gaussian, cfg, bg)
                        image_rendered = render_pkg["render"]   # [3, H, W]
                        psnr_eval_acc += psnr(image_rendered, image_gt).mean()
                    if tb_writer: tb_writer.add_scalar("block_{}/eval-PSNR".format(block_id), psnr_eval_acc/len(eval_dataset), iteration)

            # save result_gs_ply
            if iteration == cfg.iterations:
                end_time = time.time()
                local_gaussian.save_ply(os.path.join(point_cloud_path, str(block_id), "point_cloud_{:03d}.ply".format(iteration)))

    print("Block {} optimize finished, total num pts: {}".format(block_id, local_gaussian.get_xyz.shape[0]))
    elapsed_time = end_time - start_time
    with open(os.path.join(cfg.output_dirpath, "time_consumption.txt"), "a") as file:
        file.write("block_id: {}, total num pts: {}, elapsed_time:{:.6f}s\n".format(block_id, local_gaussian.get_xyz.shape[0], elapsed_time))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reconstruction Process of View-based Gaussian Splating.")
    parser.add_argument("--config", "-c", type=str, default="./configs/rubble.yaml", help="config filepath")
    parser.add_argument("--scene_dirpath", "-s", type=str, default=None, help="scene data dirpath")
    parser.add_argument("--output_dirpath", "-o", type=str, default=None, help="optimized result output dirpath")
    parser.add_argument("--block_ids", "-b", nargs="+", type=int, default=None)
    args = parser.parse_args()
    cfg = parse_cfg(args)

    scene = Scene(cfg.scene_dirpath, evaluate=cfg.evaluate, scene_scale=cfg.scene_scale)
    os.makedirs(cfg.output_dirpath, exist_ok=True)
    shutil.copy(args.config, os.path.join(cfg.output_dirpath, "config.yaml"))
    # print("Optimization result in: {}".format(cfg.output_dirpath))

    ############################ reconstruct the scene as one block ############################
    # pcd_filepath = os.path.join(cfg.scene_dirpath, "sparse/0/points3D.bin")
    # pcd = read_pcdfile(pcd_filepath, scene_scale=cfg.scene_scale)
    # views_info_list = [scene.views_info[view_id] for view_id in scene.train_views_id]
    # eval_views_info = None
    # block_bbx_expand = None
    # reconstruct(cfg, int(0), None, views_info_list, pcd, eval_views_info)

    ############################ reconstructing block by block ############################
    blocks_info_jsonpath = os.path.join(cfg.output_dirpath, "blocks_info.json")
    with open(blocks_info_jsonpath, "r") as json_file:
        blocks_info = json.load(json_file)
    num_blocks = blocks_info["num_blocks"]
    block_ids = args.block_ids if args.block_ids is not None else range(0, num_blocks)
    for block_id in block_ids:
        block_info = blocks_info[str(block_id)]
        pcd_filepath = block_info["block_pcd_filepath"]
        block_bbx_expand = np.array(block_info["bbx_expand"])
        pcd = read_pcdfile(pcd_filepath)
        views_info_list = [scene.views_info[view_id] for view_id in block_info["views_id"]]
        eval_views_info = None
        reconstruct(cfg, block_id, block_bbx_expand, views_info_list, pcd, eval_views_info)
