"""
➵ Authors : Mael Pierron, Jean-Max Agogué
➵ Date : 17/03/2026
➵ Objective : detect and count the chosen object in the image
"""

import cv2
import numpy as np

def pad_to_square(img):
    h, w = img.shape[:2]
    size = max(h, w)

    # Création d'une image noire carrée
    canvas = np.zeros((size, size, 3), dtype=img.dtype)

    # Calcul du padding
    pad_y = (size - h) // 2
    pad_x = (size - w) // 2

    # Placement de l'image au centre
    canvas[pad_y:pad_y+h, pad_x:pad_x+w] = img

    # Sauvegarde
    cv2.imwrite('mosaique.jpg', canvas)

    return canvas

# img = cv2.imread('IA/car2.png')
# pad_to_square(img)