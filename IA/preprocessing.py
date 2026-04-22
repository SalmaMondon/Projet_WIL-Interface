"""
➵ Authors : Mael Pierron, Jean-Max Agogué
➵ Date : 17/03/2026
➵ Objective : images preprocessing for the stitching
"""

import cv2
import config as cfg

def preprocessing(images):
    """
    Apply a gaussian blur on the image set for light denoising
    input: images (matrix list)
    output: newSet (matrix list)
    """
    newSet = []
    new_size = (cfg.IMG_WIDTH, cfg.IMG_HEIGHT)
    for img in images:
        # img = cv2.resize(img, new_size, interpolation = cv2.INTER_AREA)
        newSet.append(cv2.GaussianBlur(img,(cfg.BLUR,cfg.BLUR),0))
    return newSet