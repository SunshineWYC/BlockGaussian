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

import PIL
import PIL.Image
import torch
import numpy as np


def mse(img1, img2):
    return (((img1 - img2)) ** 2).view(img1.shape[0], -1).mean(1, keepdim=True)

def psnr(img1, img2):
    mse = (((img1 - img2)) ** 2).view(img1.shape[0], -1).mean(1, keepdim=True)
    return 20 * torch.log10(1.0 / torch.sqrt(mse))

def psnr_mask(img1, img2, mask):
    img1_masked = img1.view(img1.shape[0], -1)[:, (mask>0).flatten()]
    img2_masked = img2.view(img2.shape[0], -1)[:, (mask>0).flatten()]
    mse = ((img1_masked - img2_masked) ** 2).mean(1, keepdim=True)
    return 20 * torch.log10(1.0 / torch.sqrt(mse))

def read_image(filename, image_scale=1.0):
    image = PIL.Image.open(filename)
    new_width = int(image.width * image_scale)
    new_height = int(image.height * image_scale)
    image = image.resize((new_width, new_height))
    np_image = np.array(image, dtype=np.float32) / 255.0

    return np_image[:, :, :3]


def save_image(image:np.ndarray, filepath):
    image_save = PIL.Image.fromarray((image*255).astype("uint8"))
    image_save.save(filepath)
