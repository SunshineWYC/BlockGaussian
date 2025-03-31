import os
import json
import yaml
import torch
import argparse
import easydict
import numpy as np
import matplotlib.pyplot as plt
from utils.utils import load_gs_ply
from plyfile import PlyData, PlyElement
from scene.gaussian_model import GaussianModel


def calculate_block_transform(block_bbx):
    A, B, C, D = block_bbx[:4, :]
    E, F, G, H = block_bbx[4:, :]
    center = (A + G) / 2    # [3]

    axis_x = (B - A) / np.linalg.norm((B - A))
    axis_z = (D - A) / np.linalg.norm((D - A))
    axis_y = (E - A) / np.linalg.norm((E - A))

    B2W = np.zeros((4, 4), dtype=np.float32)
    B2W[:3, 0], B2W[:3, 1], B2W[:3, 2] = axis_x, axis_y, axis_z
    B2W[:3, 3] = center
    B2W[3, 3] = 1

    W2B = np.linalg.inv(B2W)
    vertices_block = (W2B[:3, :3] @ block_bbx.T).T + W2B[:3, 3]
    x_extent = abs(vertices_block[0, 0])
    y_extent = abs(vertices_block[0, 1])
    z_extent = abs(vertices_block[0, 2])

    return W2B, float(x_extent), float(y_extent), float(z_extent)


def save_gs_ply(plypath, xyz, features_dc, features_rest, opacity, scaling, rotation):
    os.makedirs(os.path.dirname(plypath), exist_ok=True)

    normals = np.zeros_like(xyz)
    f_dc = features_dc.reshape(features_dc.shape[0], -1)
    f_rest = features_rest.reshape(features_rest.shape[0], -1)

    l = ['x', 'y', 'z', 'nx', 'ny', 'nz']
    # All channels except the 3 DC
    for i in range(f_dc.shape[1]):
        l.append('f_dc_{}'.format(i))
    for i in range(f_rest.shape[1]):
        l.append('f_rest_{}'.format(i))
    l.append('opacity')
    for i in range(scaling.shape[1]):
        l.append('scale_{}'.format(i))
    for i in range(rotation.shape[1]):
        l.append('rot_{}'.format(i))
    dtype_full = [(attribute, 'f4') for attribute in l]

    elements = np.empty(xyz.shape[0], dtype=dtype_full)
    attributes = np.concatenate((xyz, normals, f_dc, f_rest, opacity, scaling, rotation), axis=1)
    elements[:] = list(map(tuple, attributes))

    elements = np.empty(xyz.shape[0], dtype=dtype_full)
    attributes = np.concatenate((xyz, normals, f_dc, f_rest, opacity, scaling, rotation), axis=1)
    elements[:] = list(map(tuple, attributes))
    el = PlyElement.describe(elements, 'vertex')
    PlyData([el]).write(plypath)


def merge_blocks(sh_degree, ply_filepaths, merged_plypath):
    xyz_all, features_dc_all, features_extra_all, opacities_all, scales_all, rots_all = [], [], [], [], [], []
    for ply_filepath in ply_filepaths:
        xyz, features_dc, features_extra, opacities, scales, rots = load_gs_ply(sh_degree, ply_filepath)
        xyz_all.append(xyz)
        features_dc_all.append(features_dc)
        features_extra_all.append(features_extra)
        opacities_all.append(opacities)
        scales_all.append(scales)
        rots_all.append(rots)
    
    xyz_all = np.concat(xyz_all, axis=0)
    features_dc_all = np.concat(features_dc_all, axis=0)
    features_extra_all = np.concat(features_extra_all, axis=0)
    opacities_all = np.concat(opacities_all, axis=0)
    scales_all = np.concat(scales_all, axis=0)
    rots_all = np.concat(rots_all, axis=0)

    print("Num points of merged scene pcd:", xyz_all.shape[0])
    save_gs_ply(merged_plypath, xyz_all, features_dc_all, features_extra_all, opacities_all, scales_all, rots_all)


def plot_rectangle(rectangle: np.ndarray, color=np.random.rand(3)):
    """
    Plot a rectangle given its vertices and fill it with color.

    Parameters:
        rectangle (np.ndarray): An array of shape [4, 2] representing the rectangle's vertices.
        color (str): The fill color of the rectangle.
    """
    # Close the rectangle by appending the first point to the end
    rectangle_closed = np.vstack([rectangle, rectangle[0]])

    # Plot and fill the rectangle
    plt.fill(rectangle_closed[:, 0], rectangle_closed[:, 1], color=color, alpha=0.3)
    plt.plot(rectangle_closed[:, 0], rectangle_closed[:, 1], color=color, alpha=0.3)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Block fusion to construct the whole scene.")
    parser.add_argument("--optimized_path", "-o", type=str, default="./output/rubble", help="optimized scene dirpath")
    parser.add_argument("--merge", action="store_true", help="generate scene merged ply file")
    args = parser.parse_args()

    config_filepath = os.path.join(args.optimized_path, "config.yaml")
    with open(config_filepath, "rb") as f:
        cfg = yaml.load(f, Loader=yaml.FullLoader)
    cfg = easydict.EasyDict(cfg)
    cfg.output_dirpath = args.optimized_path

    output_dirpath = args.optimized_path
    blocks_info_jsonpath = os.path.join(cfg.output_dirpath, "blocks_info.json")
    with open(blocks_info_jsonpath, "r") as json_file:
        blocks_info = json.load(json_file)
    sh_degree = cfg.sh_degree
    num_blocks = blocks_info["num_blocks"]

    points_counter = 0
    # prune block outliners with block bounding box
    with torch.no_grad():
        block_gaussian = GaussianModel(sh_degree=sh_degree)
        for block_id in range(0, num_blocks):
            optimized_pcd_filename = sorted(os.listdir(os.path.join(cfg.output_dirpath, "point_cloud", str(block_id))))[-1]
            print(block_id, optimized_pcd_filename)
            optimized_pcdpath = os.path.join(cfg.output_dirpath, "point_cloud", str(block_id), optimized_pcd_filename)
            block_info = blocks_info[str(block_id)]
            bbx = np.array(block_info["bbx"]) # [8, 3]
            W2B, x_extent, y_extent, z_extent = calculate_block_transform(bbx)
            W2B = torch.tensor(W2B, device="cuda")
            block_gaussian.load_ply(optimized_pcdpath)

            xyz_block = (W2B[:3, :3] @ block_gaussian.get_xyz.T).T + W2B[:3, 3]
            mask_position = (xyz_block[:, 0] >= -x_extent) & (xyz_block[:, 0] <= x_extent) & \
                            (xyz_block[:, 2] >= -z_extent) & (xyz_block[:, 2] <= z_extent) & \
                            (xyz_block[:, 1] >= -y_extent*1.2) & (xyz_block[:, 1] <= y_extent*1.2)
            print("block_id:", block_id, ", num pts before postfix:", mask_position.shape[0], ", num pts after postfix:", mask_position.sum().item())
            block_gaussian._xyz = block_gaussian._xyz[mask_position]
            block_gaussian._features_dc = block_gaussian._features_dc[mask_position]
            block_gaussian._features_rest = block_gaussian._features_rest[mask_position]
            block_gaussian._opacity = block_gaussian._opacity[mask_position]
            block_gaussian._scaling = block_gaussian._scaling[mask_position]
            block_gaussian._rotation = block_gaussian._rotation[mask_position]
            block_gaussian.save_ply(os.path.join(cfg.output_dirpath, "point_cloud_postfix", "point_cloud_{}.ply".format(block_id)))
            points_counter += block_gaussian._xyz.shape[0]
    print("Postfix over, scene total points number is: ", points_counter)

    if args.merge:
        # merge all postfix block_pcd to scene_pcd
        merged_plypath = os.path.join(cfg.output_dirpath, "point_cloud_merged.ply")
        ply_filepaths = []
        for block_id in range(0, num_blocks):
            ply_filepaths.append(os.path.join(cfg.output_dirpath, "point_cloud_postfix", "point_cloud_{}.ply".format(block_id)))
        merge_blocks(sh_degree, ply_filepaths, merged_plypath)
