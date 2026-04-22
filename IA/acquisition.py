"""
➵ Authors : Mael Pierron, Jean-Max Agogué
➵ Date : 17/03/2026
➵ Objective : image loading and storage
"""
import cv2
import os
from . import config as cfg

def acquisition():
    """
    Zeppeline data loading
    Output : images_data (matrix list)
    """
    images_data = []
    for filename in os.listdir(cfg.FOLDERPATH):
        if filename.endswith(cfg.FILETYPE):
            path = os.path.join(cfg.FOLDERPATH, filename)
            image = cv2.imread(path)
            images_data.append(image)
    
    return images_data