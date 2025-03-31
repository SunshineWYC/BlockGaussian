#
# Copyright (C) 2023, Inria
# GRAPHDECO research group, https://team.inria.fr/graphdeco
# All rights reserved.
#
# This software is free for non-commercial, research and evaluation use 
# under the terms of the LICENSE.md file.
#
# For inquiries contact  george.drettakis@inria.fr
#

import torch
import torch.nn.functional as F
from torch.autograd import Variable
from math import exp
try:
    from diff_gaussian_rasterization._C import fusedssim, fusedssim_backward
except:
    pass

C1 = 0.01 ** 2
C2 = 0.03 ** 2

class FusedSSIMMap(torch.autograd.Function):
    @staticmethod
    def forward(ctx, C1, C2, img1, img2):
        ssim_map = fusedssim(C1, C2, img1, img2)
        ctx.save_for_backward(img1.detach(), img2)
        ctx.C1 = C1
        ctx.C2 = C2
        return ssim_map

    @staticmethod
    def backward(ctx, opt_grad):
        img1, img2 = ctx.saved_tensors
        C1, C2 = ctx.C1, ctx.C2
        grad = fusedssim_backward(C1, C2, img1, img2, opt_grad)
        return None, None, grad, None

def l1_loss(network_output, gt):
    return torch.abs((network_output - gt)).mean()

def l2_loss(network_output, gt):
    return ((network_output - gt) ** 2).mean()

def gaussian(window_size, sigma):
    gauss = torch.Tensor([exp(-(x - window_size // 2) ** 2 / float(2 * sigma ** 2)) for x in range(window_size)])
    return gauss / gauss.sum()

def create_window(window_size, channel):
    _1D_window = gaussian(window_size, 1.5).unsqueeze(1)
    _2D_window = _1D_window.mm(_1D_window.t()).float().unsqueeze(0).unsqueeze(0)
    window = Variable(_2D_window.expand(channel, 1, window_size, window_size).contiguous())
    return window

def ssim(img1, img2, window_size=11, size_average=True):
    channel = img1.size(-3)
    window = create_window(window_size, channel)

    if img1.is_cuda:
        window = window.cuda(img1.get_device())
    window = window.type_as(img1)

    return _ssim(img1, img2, window, window_size, channel, size_average)

def _ssim(img1, img2, window, window_size, channel, size_average=True):
    mu1 = F.conv2d(img1, window, padding=window_size // 2, groups=channel)
    mu2 = F.conv2d(img2, window, padding=window_size // 2, groups=channel)

    mu1_sq = mu1.pow(2)
    mu2_sq = mu2.pow(2)
    mu1_mu2 = mu1 * mu2

    sigma1_sq = F.conv2d(img1 * img1, window, padding=window_size // 2, groups=channel) - mu1_sq
    sigma2_sq = F.conv2d(img2 * img2, window, padding=window_size // 2, groups=channel) - mu2_sq
    sigma12 = F.conv2d(img1 * img2, window, padding=window_size // 2, groups=channel) - mu1_mu2

    C1 = 0.01 ** 2
    C2 = 0.03 ** 2

    ssim_map = ((2 * mu1_mu2 + C1) * (2 * sigma12 + C2)) / ((mu1_sq + mu2_sq + C1) * (sigma1_sq + sigma2_sq + C2))

    if size_average:
        return ssim_map.mean()
    else:
        return ssim_map.mean(1).mean(1).mean(1)

def fast_ssim(img1, img2):
    ssim_map = FusedSSIMMap.apply(C1, C2, img1, img2)
    return ssim_map.mean()

def l1_loss_mask(image_rendered, image_gt, mask):
    mask = mask.expand_as(image_rendered)
    loss = torch.abs(image_rendered - image_gt)[mask].mean()

    return loss

def ssim_loss_mask(img1, img2, mask, window_size=11):
    channel = img1.size(-3)
    window = create_window(window_size, channel)

    if img1.is_cuda:
        window = window.cuda(img1.get_device())
    window = window.type_as(img1)

    return 1.0-_ssim_mask(img1, img2, mask, window, window_size, channel)

def _ssim_mask(img1, img2, mask, window, window_size, channel):
    mu1 = F.conv2d(img1, window, padding=window_size // 2, groups=channel)
    mu2 = F.conv2d(img2, window, padding=window_size // 2, groups=channel)

    mu1_sq = mu1.pow(2)
    mu2_sq = mu2.pow(2)
    mu1_mu2 = mu1 * mu2

    sigma1_sq = F.conv2d(img1 * img1, window, padding=window_size // 2, groups=channel) - mu1_sq
    sigma2_sq = F.conv2d(img2 * img2, window, padding=window_size // 2, groups=channel) - mu2_sq
    sigma12 = F.conv2d(img1 * img2, window, padding=window_size // 2, groups=channel) - mu1_mu2

    C1 = 0.01 ** 2
    C2 = 0.03 ** 2

    ssim_map = ((2 * mu1_mu2 + C1) * (2 * sigma12 + C2)) / ((mu1_sq + mu2_sq + C1) * (sigma1_sq + sigma2_sq + C2))
    mask = mask.expand_as(ssim_map) + 0.0
    ssim_map = ssim_map * mask

    return ssim_map.sum() / mask.sum()


def src2ref(ref_intrinsic, ref_extrinsic, ref_view_depth, dummy_intrinsic, dummy_extrinsic, dummy_view_depth, dummy_image):
    device = ref_extrinsic.device
    ref_height, ref_width = ref_view_depth.shape[0], ref_view_depth.shape[1]
    u, v = torch.meshgrid(torch.arange(ref_width, device=device), torch.arange(ref_height, device=device), indexing="xy") # u->right, v->down
    u, v = u.flatten().to(torch.float32) + 0.5, v.flatten().to(torch.float32) + 0.5

    z_ref = ref_view_depth.flatten()
    uv1 = torch.stack((u * z_ref, v * z_ref, z_ref), dim=0) # [3, H*W]
    xyz_ref = torch.matmul(torch.linalg.inv(ref_intrinsic), uv1)    # [3, H*W]
    xyz_ref_homo = torch.cat((xyz_ref, torch.ones((1, xyz_ref.shape[1]), device=device)), dim=0)    # [4, H*W]
    xyz_world = torch.matmul(torch.linalg.inv(ref_extrinsic), xyz_ref_homo) # [4, H*W]

    xyz_src = torch.matmul(dummy_extrinsic, xyz_world)[:3, :]  # [3, H*W]
    uv_src = torch.matmul(dummy_intrinsic, xyz_src)    # [3, H*W]
    u_src = (uv_src[0, :] / (uv_src[2, :]+1e-8)).view(ref_height, ref_width)
    v_src = (uv_src[1, :] / (uv_src[2, :]+1e-8)).view(ref_height, ref_width)
    
    u_src = 2.0 * (u_src / (ref_width - 1)) - 1.0
    v_src = 2.0 * (v_src / (ref_height - 1)) - 1.0
    grid = torch.stack((u_src, v_src), dim=-1).unsqueeze(0)  # [1, H, W, 2]
    reprojected_depth = torch.nn.functional.grid_sample(dummy_view_depth.unsqueeze(0).unsqueeze(0), grid, mode="bilinear", align_corners=True)   # [1, 1, H, W]
    reprojected_depth = reprojected_depth.squeeze()

    reprojected_image = torch.nn.functional.grid_sample(dummy_image.unsqueeze(0), grid, mode="bilinear", align_corners=True)
    reprojected_image = reprojected_image.squeeze(0)

    return reprojected_depth, reprojected_image


def loss_reproj(reprojected_depth, reprojected_image, image_gt):
    mask = (reprojected_depth == 0)
    mask = mask.expand_as(image_gt)
    loss = torch.abs(image_gt - reprojected_image)[mask].mean()
    return loss
