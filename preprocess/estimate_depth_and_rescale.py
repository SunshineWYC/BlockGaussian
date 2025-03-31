"""
estimate depth by DepthAnythingV2 and rescale the result aligned with colmap sparse points

"""

import os
import cv2
import json
import time
import argparse
import numpy as np
from tqdm import tqdm
from joblib import delayed, Parallel
from colmap_reader import read_model, qvec2rotmat
import warnings
warnings.filterwarnings("ignore")


def rescale_depth(key, cameras, images, points3d_ordered, depth_any_dirpath):
    image_meta = images[key]
    cam_intrinsic = cameras[image_meta.camera_id]

    # load colmap sparse points and calculate colmap depth
    pts_idx = images_metas[key].point3D_ids
    mask = pts_idx >= 0
    mask *= pts_idx < len(points3d_ordered)
    pts_idx = pts_idx[mask]
    pts = points3d_ordered[pts_idx] if len(pts_idx) > 0 else np.array([0, 0, 0])
    R = qvec2rotmat(image_meta.qvec)
    pts = np.dot(pts, R.T) + image_meta.tvec
    colmapdepth_inv = 1.0 / pts[..., 2]

    # load mono depth
    n_remove = len(image_meta.name.split('.')[-1]) + 1
    monodepthmap_inv = cv2.imread(os.path.join(depth_any_dirpath, image_meta.name[:-n_remove]+".png"), cv2.IMREAD_UNCHANGED)
    assert monodepthmap_inv is not None
    assert monodepthmap_inv.shape[0] == cam_intrinsic.height and monodepthmap_inv.shape[1] == cam_intrinsic.width
    if monodepthmap_inv.ndim != 2: monodepthmap_inv = monodepthmap_inv[..., 0]
    monodepthmap_inv = monodepthmap_inv / 255.

    # calculate scale and depth
    valid_xys = image_meta.xys[mask]
    maps = valid_xys.astype(np.float32)
    valid = ((maps[..., 0] >= 0) * 
             (maps[..., 1] >= 0) * 
             (maps[..., 0] < cam_intrinsic.width) * 
             (maps[..., 1] < cam_intrinsic.height) * (colmapdepth_inv > 0))
    
    if valid.sum() > 10:
        maps = maps[valid, :]
        colmapdepth_inv = colmapdepth_inv[valid]
        monodepth_inv = cv2.remap(monodepthmap_inv, maps[..., 0], maps[..., 1], interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)[..., 0]

        t_colmap = np.median(colmapdepth_inv)
        s_colmap = np.mean(np.abs(colmapdepth_inv - t_colmap))

        t_mono = np.median(monodepth_inv)
        s_mono = np.mean(np.abs(monodepth_inv - t_mono))
        scale = s_colmap / s_mono
        offset = t_colmap - t_mono * scale
    else:
        scale = 0
        offset = 0

    return {"image_name": image_meta.name[:-n_remove], "scale": scale, "offset": offset}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reconstruction Process of View-based Gaussian Splating.")
    parser.add_argument("--scene_dirpath", "-s", type=str, default=None, help="scene data dirpath")
    args = parser.parse_args()

    # estimate depth by Depth-Anything-V2
    image_dirpath = os.path.join(args.scene_dirpath, "images")
    depth_any_dirpath = os.path.join(args.scene_dirpath, "depth_any")
    command = "python ./preprocess/Depth-Anything-V2/run.py --encoder vitl --pred-only --grayscale --img-path {} --outdir {}".format(image_dirpath, depth_any_dirpath)
    exit_code = os.system(command)

    # read scene colmap info
    cam_intrinsics, images_metas, points3d = read_model(os.path.join(args.scene_dirpath, "sparse", "0"))
    pts_indices = np.array([points3d[key].id for key in points3d])
    pts_xyzs = np.array([points3d[key].xyz for key in points3d])
    points3d_ordered = np.zeros([pts_indices.max()+1, 3])
    points3d_ordered[pts_indices] = pts_xyzs

    depth_param_list = Parallel(n_jobs=-1, backend="threading")(
        delayed(rescale_depth)(key, cam_intrinsics, images_metas, points3d_ordered, depth_any_dirpath) for key in images_metas)

    depth_params = {
        depth_param["image_name"]: {"scale": depth_param["scale"], "offset": depth_param["offset"]}
        for depth_param in depth_param_list if depth_param != None
    }
    with open(f"{args.scene_dirpath}/sparse/0/depth_params.json", "w") as f:
        json.dump(depth_params, f, indent=4)
