import os
import json
import argparse
import numpy as np
import open3d as o3d
from tqdm import tqdm
from functools import partial
from utils.utils import parse_cfg, read_pcdfile
from scipy.spatial import ConvexHull
from scene.scene_loader import Scene
import matplotlib.pyplot as plt
from scene.colmap_loader import read_extrinsics_binary, read_extrinsics_text, read_intrinsics_binary, read_intrinsics_text
from scene.colmap_loader import read_points3D_binary_, read_points3D_text_, qvec2rotmat
from utils.general_utils import storePly, fetchPly


def fetch_local_pcd(scene_dirpath, block_pcd_filepath, views_id, scene_scale=1.0):
    assert os.path.exists(os.path.join(scene_dirpath, "sparse/0")), "sparse fold is not exist while the scene_type is colmap."
    try:
        cameras_extrinsic_file = os.path.join(scene_dirpath, "sparse/0", "images.bin")
        cam_extrinsics = read_extrinsics_binary(cameras_extrinsic_file)
    except:
        cameras_extrinsic_file = os.path.join(scene_dirpath, "sparse/0", "images.txt")
        cam_extrinsics = read_extrinsics_text(cameras_extrinsic_file)

    bin_path = os.path.join(scene_dirpath, "sparse/0/points3D.bin")
    txt_path = os.path.join(scene_dirpath, "sparse/0/points3D.txt")

    # load points3D in world coordinate
    try:
        points3D = read_points3D_binary_(bin_path, scene_scale)
    except:
        points3D = read_points3D_text_(txt_path, scene_scale)

    points3D_ids_total = set()
    for view_id in views_id:
        extr = cam_extrinsics[view_id]
        points3D_ids = extr.point3D_ids[extr.point3D_ids != -1] # the ids of current view pt2d corresponding point3D id
        points3D_ids_total.update(points3D_ids)
    
    points3D_ids_total = list(points3D_ids_total)
    num_pts = len(points3D_ids_total)
    xyzs = np.array([points3D[pt_id].xyz for pt_id in points3D_ids_total])
    rgbs = np.array([points3D[pt_id].rgb for pt_id in points3D_ids_total])
    if num_pts != 0:
        os.makedirs(os.path.dirname(block_pcd_filepath), exist_ok=True)
        storePly(block_pcd_filepath, xyzs, rgbs)

    num_pts = len(points3D_ids_total)
    return num_pts


def plot_rectangle(rectangle: np.ndarray, color=np.random.rand(3), text=None):
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

    if text is not None:
        center_x = (rectangle[0][0] + rectangle[2][0]) / 2
        center_y = (rectangle[0][1] + rectangle[2][1]) / 2
        font_size = int(abs(rectangle[0][0] - rectangle[2][0]) / 10)
        plt.text(center_x, center_y, text, fontsize=font_size, color='blue')


def minimum_area_bounding_rectangle(polygon: np.ndarray) -> np.ndarray:
    """
    Compute the minimum area bounding rectangle for a given polygon.

    Parameters:
        polygon (np.ndarray): An array of shape [N, 2] representing the polygon's vertices.

    Returns:
        np.ndarray: An array of shape [4, 2] representing the vertices of the minimum area bounding rectangle.
    """
    # Ensure the polygon is a numpy array
    polygon = np.asarray(polygon)

    # Calculate the convex hull of the polygon
    from scipy.spatial import ConvexHull
    hull = ConvexHull(polygon)
    hull_points = polygon[hull.vertices]

    # Initialize variables
    min_area = float('inf')
    best_rectangle = None

    # Loop through edges of the convex hull
    for i in range(len(hull_points)):
        # Compute the edge vector and its angle
        p1 = hull_points[i]
        p2 = hull_points[(i + 1) % len(hull_points)]
        edge = p2 - p1
        angle = np.arctan2(edge[1], edge[0])

        # Create rotation matrix to align edge with x-axis
        cos_theta = np.cos(-angle)
        sin_theta = np.sin(-angle)
        rotation_matrix = np.array([[cos_theta, -sin_theta], [sin_theta, cos_theta]])

        # Rotate all points
        rotated_points = np.dot(hull_points, rotation_matrix.T)

        # Find bounding rectangle in rotated frame
        min_x, min_y = np.min(rotated_points, axis=0)
        max_x, max_y = np.max(rotated_points, axis=0)
        area = (max_x - min_x) * (max_y - min_y)

        # Update minimum area and rectangle if needed
        if area < min_area:
            min_area = area
            best_rectangle = np.array([
                [min_x, min_y],
                [max_x, min_y],
                [max_x, max_y],
                [min_x, max_y]
            ])
            # Transform back to original coordinates
            best_rectangle = np.dot(best_rectangle, rotation_matrix)

    return best_rectangle


def cross_product(v1, v2):
    return v1[:, 0] * v2[:, 1] - v1[:, 1] * v2[:, 0]


def points_in_rotated_rectangle(points, rect_vertices):
    points = np.array(points)
    rect_vertices = np.array(rect_vertices)

    AB = rect_vertices[1] - rect_vertices[0]
    BC = rect_vertices[2] - rect_vertices[1]
    CD = rect_vertices[3] - rect_vertices[2]
    DA = rect_vertices[0] - rect_vertices[3]

    AP = points - rect_vertices[0]
    BP = points - rect_vertices[1]
    CP = points - rect_vertices[2]
    DP = points - rect_vertices[3]

    cross_AB_AP = cross_product(np.tile(AB, (points.shape[0], 1)), AP)
    cross_BC_BP = cross_product(np.tile(BC, (points.shape[0], 1)), BP)
    cross_CD_CP = cross_product(np.tile(CD, (points.shape[0], 1)), CP)
    cross_DA_DP = cross_product(np.tile(DA, (points.shape[0], 1)), DP)

    mask = (
        (cross_AB_AP <= 0) & (cross_BC_BP <= 0) & (cross_CD_CP <= 0) & (cross_DA_DP <= 0)
    ) | (
        (cross_AB_AP >= 0) & (cross_BC_BP >= 0) & (cross_CD_CP >= 0) & (cross_DA_DP >= 0)
    )

    return mask


def divide_oblique_rectangle(rect_vertices, m, n):
    def calculate_distance(P1, P2):
        return np.linalg.norm(P1 - P2)
    
    if calculate_distance(rect_vertices[0], rect_vertices[1]) >= calculate_distance(rect_vertices[1], rect_vertices[2]):
        A, B, C, D = rect_vertices
    else:
        D, A, B, C = rect_vertices

    rectangles = []
    for i in range(m):
        for j in range(n):
            p1 = A + i * (B - A) / m + j * (D - A) / n
            p2 = A + (i+1) * (B - A) / m + j * (D - A) / n
            p3 = A + (i+1) * (B - A) / m + (j+1) * (D - A) / n
            p4 = A + i * (B - A) / m + (j+1) * (D - A) / n
            rectangles.append([i, j, np.stack([p1, p2, p3, p4], axis=0)])

    return rectangles


def expand_rectangle(rect_vertices, ratio):
    center = np.mean(rect_vertices, axis=0)
    
    rect_expand_vertices = center + (rect_vertices - center) * (1 + ratio)
    return rect_expand_vertices


def select_scene_area(pts_2d, cameras_position_2d):
    fig, ax = plt.subplots(figsize=(8, 8))
    fig.canvas.manager.set_window_title("Interactive Select Scene ROI Region")
    plt.scatter(pts_2d[:, 0], pts_2d[:, 1], c='black', s=0.01, label='Points', alpha=0.05)
    plt.scatter(cameras_position_2d[:, 0], cameras_position_2d[:, 1], c='red', s=1.0, label='Camera')
    # visual_pcd_heatmap(pts_2d, bins=500, alpha=1.0)

    polygon_points = []
    polygon_line, = ax.plot([], [], 'yo-')

    def on_click(event):
        if event.inaxes != ax:
            return
        x, y = event.xdata, event.ydata
        polygon_points.append((x, y))
        if len(polygon_points) > 1:
            x_data, y_data = zip(*polygon_points)
        else:
            x_data, y_data = [x], [y]
        polygon_line.set_data(x_data, y_data)
        fig.canvas.draw()

    def on_key(event):
        if event.key == 'enter':  # press "Enter" to close polygon
            if len(polygon_points) > 2:
                polygon_points.append(polygon_points[0])
                x_data, y_data = zip(*polygon_points)
                polygon_line.set_data(x_data, y_data)
                fig.canvas.draw()
            else:
                print("At least 3 points are required to form a polygon.")

    fig.canvas.mpl_connect('button_press_event', on_click)
    fig.canvas.mpl_connect('key_press_event', on_key)
    plt.axis("equal")
    plt.axis("off")
    plt.show()
    
    return np.array(polygon_points)[:-1, :]


def visual_pcd_heatmap(pts_2d, bins, alpha=0.5):
    heatmap, xedges, yedges = np.histogram2d(pts_2d[:, 0], pts_2d[:, 1], bins=bins)
    plt.imshow(heatmap.T, extent=[xedges[0], xedges[-1], yedges[0], yedges[-1]], origin='lower', cmap='terrain', alpha=alpha)


def divide_rect(rect):
    # divide the rect along the longer edge
    edge_1_length = np.linalg.norm(rect[0] - rect[1])
    edge_2_length = np.linalg.norm(rect[0] - rect[3])

    if edge_1_length >= edge_2_length:
        mid_pt_1 = (rect[0] + rect[1]) / 2
        mid_pt_2 = (rect[2] + rect[3]) / 2

        sub_rect_1 = np.array([
            rect[0],
            mid_pt_1,
            mid_pt_2,
            rect[3]
        ])
        sub_rect_2 = np.array([
            mid_pt_1,
            rect[1],
            rect[2],
            mid_pt_2,
        ])
    else:
        mid_pt_1 = (rect[0] + rect[3]) / 2
        mid_pt_2 = (rect[1] + rect[2]) / 2

        sub_rect_1 = np.array([
            rect[0],
            rect[1],
            mid_pt_2,
            mid_pt_1,
        ])
        sub_rect_2 = np.array([
            mid_pt_1,
            mid_pt_2,
            rect[2],
            rect[3],
        ])

    return sub_rect_1, sub_rect_2


def divide_condition(rect, condition_vars_list):
    pts_2d_init, num_points_thresh = condition_vars_list
    # select points in this block
    mask = points_in_rotated_rectangle(pts_2d_init, rect)

    if mask.sum() > num_points_thresh:
        return False
    else:
        print("block init point number:", mask.sum())
        return True


def recursive_split(rectangle, blocks, tree_depth, max_tree_depth, condition_vars_list):
    flag = divide_condition(rectangle, condition_vars_list)
    if flag or tree_depth > max_tree_depth:
        blocks.append(rectangle)
    else:
        rect_1, rect_2 = divide_rect(rectangle)
        recursive_split(rect_1, blocks, tree_depth+1, max_tree_depth, condition_vars_list)
        recursive_split(rect_2, blocks, tree_depth+1, max_tree_depth, condition_vars_list)


def scene_partion(cfg, vertical_axis="z"):
    vertical_axis_idx = {"x":0, "y":1, "z":2}[vertical_axis]
    scene = Scene(cfg.scene_dirpath, evaluate=cfg.evaluate, scene_scale=cfg.scene_scale)
    cameras_positions = [np.linalg.inv(scene.views_info[view_id].extrinsic)[:3, 3] for view_id in scene.train_views_id]
    cameras_positions_3d = np.stack(cameras_positions, axis=0)  # [N, 3]

    #################### calculate scene bbx in 2d space #####################
    pts_bin_path = os.path.join(cfg.scene_dirpath, "sparse/0/points3D.bin")
    points3D = read_points3D_binary_(pts_bin_path, scale=cfg.scene_scale)
    points3D_ids = np.array(list(points3D.keys()))
    points3D_xyz = np.stack([pt.xyz for pt in points3D.values()], axis=0)

    points = np.asarray(points3D_xyz)
    # filter points to remove noise
    point_cloud = o3d.geometry.PointCloud()
    point_cloud.points = o3d.utility.Vector3dVector(points3D_xyz)
    cl, ind = point_cloud.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
    point_cloud = point_cloud.select_by_index(ind)
    points = np.asarray(point_cloud.points)

    # visual bbx in 3D space, just for visual
    # obb = point_cloud.get_oriented_bounding_box()
    # obb.color = [0, 0, 0]
    # frame = o3d.geometry.TriangleMesh.create_coordinate_frame(size=100.0, origin=[0, 0, 0])  # x-red, y-green, z-blue
    # geometries = [point_cloud, frame, obb] # [visual_pcd, frame]
    # geometries.extend(build_camera_geometry(list(scene.views_info.values()), (1.0, 0, 0), visual_scale=0.1))
    # o3d.visualization.draw_geometries(geometries)

    # calculate bounding rect in 2D plane, for scene ["building", "rubble", "sciart", "residece"], project pts to ground plane
    if vertical_axis == "z":
        cameras_position_2d = np.stack((cameras_positions_3d[:, 0], cameras_positions_3d[:, 1]), axis=1)
        pts_2d = np.stack((points[:, 0], points[:, 1]), axis=1)
        pts_2d_init = np.stack((points3D_xyz[:, 0], points3D_xyz[:, 1]), axis=1)
    elif vertical_axis == "y":
        cameras_position_2d = np.stack((cameras_positions_3d[:, 0], cameras_positions_3d[:, 2]), axis=1)
        pts_2d = np.stack((points[:, 0], points[:, 2]), axis=1)
        pts_2d_init = np.stack((points3D_xyz[:, 0], points3D_xyz[:, 2]), axis=1)
    elif vertical_axis == "x":
        cameras_position_2d = np.stack((cameras_positions_3d[:, 1], cameras_positions_3d[:, 2]), axis=1)
        pts_2d = np.stack((points[:, 1], points[:, 2]), axis=1)
        pts_2d_init = np.stack((points3D_xyz[:, 1], points3D_xyz[:, 2]), axis=1)
    else:
        raise ValueError("vertical_axis should be x/y/z")
    
    polygon_pts = select_scene_area(pts_2d, cameras_position_2d)
    bounding_rect = minimum_area_bounding_rectangle(polygon_pts)

    # visual 2D Scene ROI region
    plt.figure("Scene ROI Aera", figsize=(8, 8))
    plt.scatter(pts_2d[:, 0], pts_2d[:, 1], c='black', s=0.01, label='Points', alpha=0.05)
    plt.scatter(cameras_position_2d[:, 0], cameras_position_2d[:, 1], c='red', s=0.5, label='Camera')
    plot_rectangle(bounding_rect, color=[0, 1, 0])
    plt.axis("equal")
    plt.axis("off")
    plt.savefig(os.path.join(cfg.output_dirpath, "ROI_region.png"))
    plt.show()

    ################ divide scene_bounding rect to blocks by binary tree #################
    plt.figure("Scene Partion Blocks", figsize=(8, 8))
    plt.scatter(pts_2d[:, 0], pts_2d[:, 1], c='black', s=0.01, label='Points', alpha=0.3)
    plt.scatter(cameras_position_2d[:, 0], cameras_position_2d[:, 1], c='red', s=0.5, label='Camera')
    max_tree_depth = cfg.max_tree_depth # hyperparam, upper limit of number of block is 2**max_tree_depth
    num_points_thresh = cfg.num_points_thresh   # hyperparam
    camera_images_info = read_extrinsics_binary(os.path.join(cfg.scene_dirpath, "sparse/0/images.bin"))

    # recursively divide scene bounding box to blocks
    block_rects = []
    condition_vars_list = [pts_2d_init, num_points_thresh]
    recursive_split(bounding_rect, block_rects, 0, max_tree_depth, condition_vars_list)
    print("candidate block number:", len(block_rects))

    blocks_info_dict = {}
    block_counter = 0
    # expand block, assign views for each block and save initial points
    for block_idx, block_rect in enumerate(block_rects):
        print("###"*20)
        print("Candidate block idx: {}".format(block_idx))

        rect_expand = expand_rectangle(block_rect, ratio=cfg.expand_ratio)  # [4, 2]
        mask = points_in_rotated_rectangle(pts_2d_init, rect_expand)

        if mask.sum() < 2000:
            print("Too little sparse pcd in this block, filtered.")
            continue

        # calculate 3D bbx for current block
        pts_block = points3D_xyz[mask]
        vertical_axis_min, vertical_axis_max = np.percentile(pts_block[:, vertical_axis_idx], 1), np.percentile(pts_block[:, vertical_axis_idx], 99)
        vertical_axis_max = vertical_axis_max + (vertical_axis_max - vertical_axis_min) * 0.2
        vertical_axis_min = vertical_axis_min - (vertical_axis_max - vertical_axis_min) * 0.2
        bbx = np.zeros((8, 3))
        bbx[:4, :2], bbx[:4, 2] = block_rect, np.array([vertical_axis_min]*4)
        bbx[4:, :2], bbx[4:, 2] = block_rect, np.array([vertical_axis_max]*4)
        bbx_expand = np.zeros((8, 3))
        bbx_expand[:4, :2], bbx_expand[:4, 2] = rect_expand, np.array([vertical_axis_min]*4)
        bbx_expand[4:, :2], bbx_expand[4:, 2] = rect_expand, np.array([vertical_axis_max]*4)
        if vertical_axis == "x":
            bbx[:, [0, 1, 2]] = bbx[:, [2, 0, 1]]
            bbx_expand[:, [0, 1, 2]] = bbx_expand[:, [2, 0, 1]]
        elif vertical_axis == "y":
            bbx[:, [0, 1, 2]] = bbx[:, [0, 2, 1]]
            bbx_expand[:, [0, 1, 2]] = bbx_expand[:, [0, 2, 1]]
        elif vertical_axis == "z":
            bbx[:, [0, 1, 2]] = bbx[:, [0, 1, 2]]
            bbx_expand[:, [0, 1, 2]] = bbx_expand[:, [0, 1, 2]]
        else:
            raise ValueError("vertical_axis should be x/y/z")

        # select view for this block, silly implement, optimize with multiprocess
        block_points_ids = points3D_ids[mask]
        block_related_image_ids = set()
        for pt_id in block_points_ids:
            block_related_image_ids.update(list(map(int, points3D[pt_id].image_ids)))
        block_image_ids = []
        for image_id in list(block_related_image_ids):
            cover_ratio_view = len(set(camera_images_info[image_id].point3D_ids) & set(block_points_ids)) / len(set(camera_images_info[image_id].point3D_ids))
            cover_ratio_block = len(set(camera_images_info[image_id].point3D_ids) & set(block_points_ids)) / len(set(block_points_ids))
            if cover_ratio_view > cfg.cover_ratio_thresh or cover_ratio_block > 0.1:
                block_image_ids.append(image_id)

        print("num views: {}, num pts in block: {}".format(len(block_image_ids), mask.sum()))
        # filter block with too little points or views
        if len(block_image_ids) < 20:
            print("Too little view related to this block, filtered.")
            continue

        # fetch and save block_pcd by block_views_id, not by pts in block
        block_pcd_filepath = os.path.join(cfg.output_dirpath, "block_init_pcd/block_{:03d}_init_pcd.ply".format(block_counter))
        num_pts = fetch_local_pcd(cfg.scene_dirpath, block_pcd_filepath, block_image_ids, cfg.scene_scale)
        print("Selected, block_id: {}, block sparse pcd num: {}, initial point num: {}, num views: {}".format(
            block_counter, mask.sum(), num_pts, len(block_image_ids)))
        # plot bbx in scene 2d canvas
        plot_rectangle(block_rect, color=np.random.rand(3), text=None)    # text=str(block_counter)

        # build block_info
        blocks_info_dict[block_counter] = {
            "bbx": bbx.tolist(),
            "bbx_expand": bbx_expand.tolist(),
            "views_id": list(block_image_ids),
            # "pt3D_ids": block_points_ids.tolist(),
            "num_views": len(block_image_ids),
            "num_pts": len(block_points_ids.tolist()),
            "scene_scale": cfg.scene_scale,
            "block_pcd_filepath": block_pcd_filepath
        }
        block_counter += 1

    print("Scene partion finished, valid block num: {}".format(block_counter))

    # save blocks_info
    blocks_info_dict["num_blocks"] = block_counter
    json_filepath = os.path.join(cfg.output_dirpath, "blocks_info.json")
    with open(json_filepath, "w") as json_file:
        json.dump(blocks_info_dict, json_file, indent=4)

    plt.axis("equal")
    plt.axis("off")
    plt.savefig(os.path.join(cfg.output_dirpath, "Partition_Results.png"))
    plt.show()


def build_camera_geometry(views_info_list, colors, visual_scale):
    geometries = []
    for view_info in views_info_list:
        cameraLines = o3d.geometry.LineSet.create_camera_visualization(
            view_width_px=view_info.image_width, 
            view_height_px=view_info.image_height,
            intrinsic=view_info.intrinsic, extrinsic=view_info.extrinsic, scale=visual_scale)
        cameraLines.colors = o3d.utility.Vector3dVector(np.array([colors]*8))
        geometries.append(cameraLines)

    return geometries


def visual_scene_partion(cfg):
    scene = Scene(cfg.scene_dirpath, evaluate=cfg.evaluate, scene_scale=cfg.scene_scale)
    geometries = []

    blocks_info_jsonpath = os.path.join(cfg.output_dirpath, "blocks_info.json")
    with open(blocks_info_jsonpath, "r") as json_file:
        blocks_info = json.load(json_file)

    ############################# visual one block info #############################
    block_id = 0
    block_info = blocks_info[str(block_id)]
    init_block_pcd = read_pcdfile(block_info["block_pcd_filepath"])
    point_cloud_block = o3d.geometry.PointCloud()
    point_cloud_block.points = o3d.utility.Vector3dVector(init_block_pcd.points)
    point_cloud_block.colors = o3d.utility.Vector3dVector(init_block_pcd.colors)
    geometries.append(point_cloud_block)

    scene_views_info_list = [scene.views_info[view_id] for view_id in scene.train_views_id]
    block_views_info_list = [scene.views_info[view_id] for view_id in block_info["views_id"]]
    geometries.extend(build_camera_geometry(block_views_info_list, [1, 1, 0], visual_scale=3.0))

    other_views_info_list = list(set(scene_views_info_list) - set(block_views_info_list))
    geometries.extend(build_camera_geometry(other_views_info_list, [0, 0, 1], visual_scale=3.0))

    from utils.utils import cal_local_cam_extent
    block_extent = cal_local_cam_extent(block_views_info_list)
    scene_extent = cal_local_cam_extent(scene_views_info_list)
    print("scene_cam_extent: {}, block_cam_extent: {}".format(block_extent, scene_extent))

    bbx = np.array(block_info["bbx_expand"])
    lines = np.array([[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]])
    line_set = o3d.geometry.LineSet()
    line_set.points = o3d.utility.Vector3dVector(bbx)
    line_set.lines = o3d.utility.Vector2iVector(lines)
    colors = [[1, 0, 0] for _ in range(len(lines))]
    line_set.colors = o3d.utility.Vector3dVector(colors)
    geometries.append(line_set)

    ################### visual all extend bbx of blocks ########################
    # pcd_bin_path = os.path.join(cfg.scene_dirpath, "sparse/0/points3D.bin")
    # pcd_scene = read_pcdfile(pcd_bin_path)
    # point_cloud = o3d.geometry.PointCloud()
    # point_cloud.points = o3d.utility.Vector3dVector(pcd_scene.points * cfg.scene_scale)
    # point_cloud.colors = o3d.utility.Vector3dVector(pcd_scene.colors)
    # geometries.append(point_cloud)

    # blocks_bbx = []
    # for block_info in blocks_info.values():
    #     bbx = np.array(block_info["bbx"])
    #     lines = np.array([[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]])
    #     line_set = o3d.geometry.LineSet()
    #     line_set.points = o3d.utility.Vector3dVector(bbx)
    #     line_set.lines = o3d.utility.Vector2iVector(lines)
    #     colors = [[1, 0, 0] for _ in range(len(lines))]
    #     line_set.colors = o3d.utility.Vector3dVector(colors)
    #     blocks_bbx.append(line_set)
    # geometries.extend(blocks_bbx)

    o3d.visualization.draw_geometries(geometries)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reconstruction Process of View-based Gaussian Splating.")
    parser.add_argument("--config", "-c", type=str, default="./configs/rubble.yaml", help="config filepath")
    parser.add_argument("--scene_dirpath", "-s", type=str, default=None, help="scene data dirpath")
    parser.add_argument("--output_dirpath", "-o", type=str, default=None, help="optimized result output dirpath")
    args = parser.parse_args()
    cfg = parse_cfg(args)

    os.makedirs(cfg.output_dirpath, exist_ok=True)
    scene_partion(cfg, vertical_axis=cfg.vertical_axis)

    # visualize scene_partition results
    # visual_scene_partion(cfg)
