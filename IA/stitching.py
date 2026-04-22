"""
➵ Authors : Mael Pierron, Jean-Max Agogué
➵ Date : 17/03/2026
➵ Objective : Image stitching 
"""

import cv2
import config

def stitching(images):
    """
    Image stitching currently using OpenCV.
    Input : images to stitch (matrix list)
    Output : stitched image (Matrix)
    """
    stitcher = cv2.Stitcher_create(mode=cv2.Stitcher_SCANS)
    stitcher.setRegistrationResol(config.RESOLUTION)
    status, stitched = stitcher.stitch(images)
    if status == 0:
        return stitched
    else:
        raise RuntimeError("[INFO] image stitching failed ({})".format(status))

