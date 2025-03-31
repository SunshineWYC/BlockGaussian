import os
import yaml
import json
import torch
import argparse
import easydict
from PIL import Image
from tqdm import tqdm
from utils.lpipsPyTorch import lpips
from utils.image_utils import psnr
from utils.loss_utils import ssim
import torchvision.transforms.functional as tf


def evaluate(scene_dirpath, output_dirpath, split, result_dirname="render", train_eval_split=False):
    render_dirpath = os.path.join(output_dirpath, result_dirname, split, "rendered")
    if train_eval_split and split == "eval":
        gt_dirpath = os.path.join(scene_dirpath.replace("train", "val"), "images")
    else:
        gt_dirpath = os.path.join(scene_dirpath, "images")

    per_view_metrics = {}
    ssims, psnrs, lpipss = [], [], []

    for image_name in tqdm(sorted(os.listdir(render_dirpath)), desc="Evaluating"):
        image_render = Image.open(os.path.join(render_dirpath, image_name))
        image_gt = Image.open(os.path.join(gt_dirpath, image_name.replace("png", "jpg")))
        if image_render.width != image_gt.width:
            image_gt = image_gt.resize((image_render.width, image_render.height))
        image_render = tf.to_tensor(image_render).unsqueeze(0)[:, :3, :, :].cuda()
        image_gt = tf.to_tensor(image_gt).unsqueeze(0)[:, :3, :, :].cuda()
        ssims.append(ssim(image_render, image_gt))
        psnrs.append(psnr(image_render, image_gt))
        lpipss.append(lpips(image_render, image_gt, net_type='vgg'))

        per_view_metrics[image_name] = {
            "PSNR": psnrs[-1].item(),
            "SSIM": ssims[-1].item(),
            "LPIPS": lpipss[-1].item()}

    scene_PSNR = torch.tensor(psnrs).mean().item()
    scene_SSIM = torch.tensor(ssims).mean().item()
    scene_LPIPS = torch.tensor(lpipss).mean().item()

    scene_metrics = {
        "PSNR": scene_PSNR,
        "SSIM": scene_SSIM,
        "LPIPS": scene_LPIPS
    }

    with open(os.path.join(output_dirpath, result_dirname, split, "result.json"), "w") as file:
        json.dump(scene_metrics, file, indent=True)
    with open(os.path.join(output_dirpath, result_dirname, split, "per_view.json"), "w") as file:
        json.dump(per_view_metrics, file, indent=True)

    return scene_metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Metrics calculation script parameters.")
    parser.add_argument("--optimized_path", "-o", type=str, default="./output/rubble_006", help="optimized scene dirpath")
    parser.add_argument("--train_eval_split", action="store_true", help="train and eval is stored sperately")
    parser.add_argument("--eval_only", action="store_true", help="donot cal metrics on train-views")
    args = parser.parse_args()

    config_filepath = os.path.join(args.optimized_path, "config.yaml")
    with open(config_filepath, "rb") as f:
        cfg = yaml.load(f, Loader=yaml.FullLoader)
    cfg = easydict.EasyDict(cfg)
    cfg.output_dirpath = args.optimized_path

    print(args.optimized_path)
    train_view_metrics, eval_view_metrics = {}, {}
    eval_view_metrics = evaluate(cfg.scene_dirpath, cfg.output_dirpath, "eval", result_dirname="render", train_eval_split=args.train_eval_split)
    print("eval_view metrics: ", eval_view_metrics)
    if not args.eval_only:
        train_view_metrics = evaluate(cfg.scene_dirpath, cfg.output_dirpath, "train", result_dirname="render", train_eval_split=args.train_eval_split)
        print("train_view metrics: ", train_view_metrics)
