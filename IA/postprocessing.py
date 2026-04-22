"""
➵ Authors : Mael Pierron, Jean-Max Agogué
➵ Date : 01/04/2026
➵ Objective : Upgrade the image quality
"""

import cv2
import numpy as np

def postprocessing(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mask = (gray > 10).astype(np.uint8)
    h, w = mask.shape
    heights = [0] * w
    best_area = 0
    best_rect = (0, 0, 0, 0)
    for i in range(h):
        for j in range(w):
            heights[j] = heights[j] + 1 if mask[i][j] == 1 else 0
        stack = []
        for j in range(w + 1):
            curr_height = heights[j] if j < w else 0
            while stack and curr_height < heights[stack[-1]]:  
                top = stack.pop()
                width = j if not stack else j - stack[-1] - 1
                area = heights[top] * width
                if area > best_area:
                    best_area = area
                    x = 0 if not stack else stack[-1] + 1
                    y = i - heights[top] + 1
                    best_rect = (x, y, width, heights[top])
            stack.append(j)
    x, y, w, h = best_rect
    return image[y:y+h, x:x+w]