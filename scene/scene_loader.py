import os
import cv2
import PIL
import torch
import random
import numpy as np
from scene.colmap_loader import read_colmap_views_info
from concurrent.futures import ThreadPoolExecutor, as_completed


class SceneDataset(torch.utils.data.Dataset):
    def __init__(self, views_info_list, image_scale=1.0, scene_scale=1.0, view_count=None, preload=False):
        super().__init__()
        self.image_scale = image_scale
        self.scene_scale = scene_scale
        self.view_count = len(views_info_list) if view_count is None else view_count
        self.views_info_list = views_info_list
        self.preload = preload
        if self.preload:
            self.views_data = self._preload_data()

    def __len__(self):
        return self.view_count

    def _read_image(self, image_filepath, image_scale):
        image = PIL.Image.open(image_filepath)
        new_width = int(image.width * image_scale)
        new_height = int(image.height * image_scale)
        image = image.resize((new_width, new_height))
        np_image = np.array(image, dtype=np.float32) / 255.0
        return np_image[:, :, :3], new_height, new_width

    def _load_single_sample(self, view_info):
        extrinsic = view_info.extrinsic
        image, new_height, new_width = self._read_image(view_info.image_filepath, self.image_scale)
        height_scale = new_height / view_info.image_height
        width_scale = new_width / view_info.image_width
        intrinsic = view_info.intrinsic.copy()
        intrinsic[:1, :] *= width_scale
        intrinsic[1:2, :] *= height_scale

        intrinsic = torch.tensor(intrinsic)
        extrinsic = torch.tensor(extrinsic)
        image = torch.tensor(image).permute(2, 0, 1)    # [3, H, W]

        if view_info.depth_filepath is not None:
            scale, offset = view_info.depth_param["scale"], view_info.depth_param["offset"]
            depth_mono_inv = cv2.imread(view_info.depth_filepath, cv2.IMREAD_UNCHANGED)
            if depth_mono_inv.ndim != 2: depth_mono_inv = depth_mono_inv[..., 0]
            depth_mono_inv = cv2.resize(depth_mono_inv, (image.shape[2], image.shape[1]), interpolation=cv2.INTER_NEAREST) / 255.
            depth_inv = depth_mono_inv * scale + offset
            depth_inv = torch.tensor(depth_inv / self.scene_scale)
        else:
            depth_inv = 'none'

        return {"extrinsic": extrinsic,
                "intrinsic": intrinsic,
                "image_height": image.shape[1],
                "image_width": image.shape[2],
                "image": image,
                "depth_inv": depth_inv,
                "image_filepath": view_info.image_filepath}

    def _preload_data(self):
        num_views = len(self.views_info_list)
        views_data = [None] * num_views
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(self._load_single_sample, view_info): idx for idx, view_info in enumerate(self.views_info_list)}
            for future in as_completed(futures):
                idx = futures[future]
                views_data[idx] = future.result()
        return views_data

    def __getitem__(self, index):
        idx = index % len(self.views_info_list)
        if not self.preload:
            view_info = self.views_info_list[idx]
            return self._load_single_sample(view_info)
        else:
            return self.views_data[idx]


class Scene:
    def __init__(self, scene_dirpath, evaluate=False, scene_scale=1.0):
        self.scene_scale = scene_scale
        self.views_info, self.train_views_id, self.eval_views_id = read_colmap_views_info(scene_dirpath, evaluate, scene_scale)
