import os
import math
import torch
import numpy as np
from utils.graphics_utils import getWorld2ViewCUDA, getProjectionMatrixCUDA


class ViewInfo:
    def __init__(self, view_id, extrinsic, intrinsic, image_height, image_width, image_filepath, **kwargs):
        self.view_id = view_id
        self.extrinsic = extrinsic
        self.intrinsic = intrinsic
        self.image_height = image_height
        self.image_width = image_width
        self.image_filepath = image_filepath

        for key, value in kwargs.items():
            setattr(self, key, value)

    def __getattr__(self, name):
        return None


class RenderCamera(object):
    def __init__(self, image_height, image_width, FoVy, FoVx, extrinsic, intrinsic, world_view_transform, full_proj_transform):
        self.image_width = image_width
        self.image_height = image_height
        self.FoVy = FoVy
        self.FoVx = FoVx
        self.extrinsic = extrinsic
        self.intrinsic = intrinsic
        self.world_view_transform = world_view_transform
        self.full_proj_transform = full_proj_transform
        view_inv = torch.inverse(self.world_view_transform)
        self.camera_center = view_inv[3][:3]


def get_render_camera(image_height, image_width, extrinsic, intrinsic, disturb=None, trans=torch.tensor([0.0, 0.0, 0.0]).cuda(), scale=1.0, znear=0.01, zfar=100.0):
    R = extrinsic[:3, :3]
    T = extrinsic[:3, 3]

    fx = intrinsic[0, 0]
    fy = intrinsic[1, 1]
    FoVx = 2 * math.atan(image_width / (2 * fx))
    FoVy = 2 * math.atan(image_height / (2 * fy))

    world_view_transform = getWorld2ViewCUDA(R, T, trans, scale, disturb).permute(1, 0)
    projection_matrix = getProjectionMatrixCUDA(znear=znear, zfar=zfar, fovX=FoVx, fovY=FoVy).transpose(0, 1)
    full_proj_transform = (world_view_transform.unsqueeze(0).bmm(projection_matrix.unsqueeze(0))).squeeze(0)

    return RenderCamera(image_height=image_height,
                        image_width=image_width,
                        FoVy=FoVy,
                        FoVx=FoVx,
                        extrinsic=world_view_transform.permute(1, 0),
                        intrinsic=intrinsic,
                        world_view_transform=world_view_transform,
                        full_proj_transform=full_proj_transform)
