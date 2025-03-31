import os
import math
import json
import yaml
import torch
import easydict
import numpy as np
from PIL import Image
from plyfile import PlyData, PlyElement
from utils.general_utils import BasicPointCloud
from scene.colmap_loader import read_points3D_binary, read_points3D_text


def parse_cfg(args) -> easydict.EasyDict:
    if not os.path.exists(args.config):
        raise FileNotFoundError(f"config does not exist: {args.config}")

    with open(args.config, "rb") as f:
        cfg = yaml.load(f, Loader=yaml.FullLoader)
        if hasattr(args, "scene_dirpath") and args.scene_dirpath is not None: cfg["scene_dirpath"] = args.scene_dirpath 
        if hasattr(args, "output_dirpath") and args.output_dirpath is not None: cfg["output_dirpath"] = args.output_dirpath
    cfg = easydict.EasyDict(cfg)

    if not os.path.exists(cfg.scene_dirpath):
        raise FileNotFoundError(f"scene_dirpath does not exist: {cfg.scene_dirpath}")

    return cfg


def save_cfg(cfg, block_id):
    json_filepath = os.path.join(cfg.output_dirpath, "configs", "block_{:03d}_config.json".format(block_id))
    os.makedirs(os.path.dirname(json_filepath), exist_ok=True)
    with open(json_filepath, "w", encoding="utf-8") as json_file:
        json.dump(dict(cfg), json_file, indent=4, ensure_ascii=False)


def cal_local_cam_extent(views):
    def get_center_and_diag(cam_centers):
        cam_centers = np.hstack(cam_centers)
        avg_cam_center = np.mean(cam_centers, axis=1, keepdims=True)
        center = avg_cam_center
        dist = np.linalg.norm(cam_centers - center, axis=0, keepdims=True)
        diagonal = np.max(dist)
        return center.flatten(), diagonal
    
    cam_centers = []
    for view in views:
        W2C = view.extrinsic
        C2W = np.linalg.inv(W2C)
        cam_centers.append(C2W[:3, 3:4])
    
    center, diagonal = get_center_and_diag(cam_centers)
    extent = diagonal * 1.1

    return extent


def visual_image_rendered(image, output_filepath):
    image_visual = image.detach().cpu().numpy().transpose(1, 2, 0)
    image_visual = (image_visual * 255).astype(np.uint8)
    Image.fromarray(image_visual).save(output_filepath)


def fetch_ply(path, scene_scale=1.0):
    plydata = PlyData.read(path)
    vertices = plydata['vertex']
    positions = np.vstack([vertices['x'], vertices['y'], vertices['z']]).T * scene_scale
    colors = np.vstack([vertices['red'], vertices['green'], vertices['blue']]).T / 255.0
    normals = np.vstack([vertices['nx'], vertices['ny'], vertices['nz']]).T
    return BasicPointCloud(points=positions, colors=colors, normals=normals)


def read_pcdfile(pcd_filepath, scene_scale=1.0):
    if pcd_filepath.endswith(".bin"):
        xyzs, rgbs, _ = read_points3D_binary(pcd_filepath)
        pcd = BasicPointCloud(points=xyzs*scene_scale, colors=rgbs/255.0, normals=None)
    elif pcd_filepath.endswith(".txt"):
        xyzs, rgbs, _ = read_points3D_text(pcd_filepath)
        pcd = BasicPointCloud(points=xyzs*scene_scale, colors=rgbs/255.0, normals=None)
    elif pcd_filepath.endswith(".ply"):
        pcd = fetch_ply(pcd_filepath, scene_scale)
    else:
        raise "pcd_filepath should be .bin or .txt generated from COLMAP-SFM, or .ply format"
    return pcd


def load_gs_ply(sh_degree, ply_filepath):
    plydata = PlyData.read(ply_filepath)
    xyz = np.stack((np.asarray(plydata.elements[0]["x"]),
                    np.asarray(plydata.elements[0]["y"]),
                    np.asarray(plydata.elements[0]["z"])),  axis=1)
    opacities = np.asarray(plydata.elements[0]["opacity"])[..., np.newaxis]

    features_dc = np.zeros((xyz.shape[0], 3, 1))
    features_dc[:, 0, 0] = np.asarray(plydata.elements[0]["f_dc_0"])
    features_dc[:, 1, 0] = np.asarray(plydata.elements[0]["f_dc_1"])
    features_dc[:, 2, 0] = np.asarray(plydata.elements[0]["f_dc_2"])

    extra_f_names = [p.name for p in plydata.elements[0].properties if p.name.startswith("f_rest_")]
    extra_f_names = sorted(extra_f_names, key = lambda x: int(x.split('_')[-1]))
    assert len(extra_f_names)==3*(sh_degree + 1) ** 2 - 3
    features_extra = np.zeros((xyz.shape[0], len(extra_f_names)))
    for idx, attr_name in enumerate(extra_f_names):
        features_extra[:, idx] = np.asarray(plydata.elements[0][attr_name])
    # Reshape (P,F*SH_coeffs) to (P, F, SH_coeffs except DC)
    features_extra = features_extra.reshape((features_extra.shape[0], 3, (sh_degree + 1) ** 2 - 1))

    scale_names = [p.name for p in plydata.elements[0].properties if p.name.startswith("scale_")]
    scale_names = sorted(scale_names, key = lambda x: int(x.split('_')[-1]))
    scales = np.zeros((xyz.shape[0], len(scale_names)))
    for idx, attr_name in enumerate(scale_names):
        scales[:, idx] = np.asarray(plydata.elements[0][attr_name])

    rot_names = [p.name for p in plydata.elements[0].properties if p.name.startswith("rot")]
    rot_names = sorted(rot_names, key = lambda x: int(x.split('_')[-1]))
    rots = np.zeros((xyz.shape[0], len(rot_names)))
    for idx, attr_name in enumerate(rot_names):
        rots[:, idx] = np.asarray(plydata.elements[0][attr_name])

    return xyz, features_dc, features_extra, opacities, scales, rots
