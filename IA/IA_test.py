"""
➵ Authors : Mael Pierron, Jean-Max Agogué
➵ Date : 17/03/2026
➵ Objective : Load DroneNet and run car detection (inference only)
"""

import torch
import torch.nn as nn
from torchvision import transforms
from PIL import Image
import numpy as np
import cv2

# ============================================================
# CONFIGURATION
# ============================================================
MODEL_PATH     = 'IA/drone_car_model.pth'
GRID_SIZE      = 32
IMG_SIZE       = 256
NMS_THRESHOLD  = 0.4
CONF_THRESHOLD = 0.02

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ============================================================
# ARCHITECTURE
# ============================================================
class ConvBlock(nn.Module):
    def __init__(self, in_f, out_f, pool=False):
        super().__init__()
        layers = [
            nn.Conv2d(in_f, out_f, 3, padding=1, bias=False),
            nn.BatchNorm2d(out_f),
            nn.ReLU(inplace=True),
        ]
        if pool:
            layers.append(nn.MaxPool2d(2))
        self.block = nn.Sequential(*layers)

    def forward(self, x):
        return self.block(x)


class DroneNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.c1      = ConvBlock(3,   32,  pool=True)
        self.c2      = ConvBlock(32,  64,  pool=True)
        self.c3      = ConvBlock(64,  128, pool=True)
        self.c4      = ConvBlock(128, 256, pool=True)
        self.c5      = ConvBlock(256, 256, pool=False)
        self.lateral = nn.Conv2d(256, 128, kernel_size=1)
        self.fusion  = ConvBlock(256, 128)
        self.head    = nn.Conv2d(128, 5,   kernel_size=1)

    def forward(self, x):
        x  = self.c1(x)
        x  = self.c2(x)
        p3 = self.c3(x)
        x  = self.c4(p3)
        x  = self.c5(x)
        x  = self.lateral(x)
        x  = nn.functional.interpolate(x, scale_factor=2, mode='nearest')
        x  = torch.cat([x, p3], dim=1)
        x  = self.fusion(x)
        return torch.sigmoid(self.head(x))


# ============================================================
# CHARGEMENT DU MODÈLE
# ============================================================
model = DroneNet().to(device)
model.load_state_dict(torch.load(MODEL_PATH, map_location=device))
model.eval()


# ============================================================
# NMS
# ============================================================
def compute_iou(box, boxes):
    inter = (
        (torch.min(box[2], boxes[:, 2]) - torch.max(box[0], boxes[:, 0])).clamp(0) *
        (torch.min(box[3], boxes[:, 3]) - torch.max(box[1], boxes[:, 1])).clamp(0)
    )
    area_box   = (box[2] - box[0]) * (box[3] - box[1])
    area_boxes = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    return inter / (area_box + area_boxes - inter + 1e-7)


def nms(boxes, scores, iou_threshold=NMS_THRESHOLD):
    order, kept = scores.argsort(descending=True), []
    while order.numel() > 0:
        i = order[0].item()
        kept.append(i)
        if order.numel() == 1:
            break
        rest  = order[1:]
        order = rest[compute_iou(boxes[i], boxes[rest]) < iou_threshold]
    return kept


# ============================================================
# DETECTION
# ============================================================
def detect(image_input, threshold=CONF_THRESHOLD):
    """
    Détecte les voitures dans une image et retourne les boîtes après NMS.
    Accepte : chemin (str), NumPy array (BGR), ou PIL Image.
    Retourne : [{'box': [x1, y1, x2, y2], 'score': float}, ...]
    """
    try:
        if isinstance(image_input, str):
            raw_img = Image.open(image_input).convert("RGB")
        elif isinstance(image_input, np.ndarray):
            raw_img = Image.fromarray(cv2.cvtColor(image_input, cv2.COLOR_BGR2RGB))
        elif hasattr(image_input, "convert"):
            raw_img = image_input.convert("RGB")
        else:
            raise ValueError(f"Format non supporté : {type(image_input)}")
    except Exception as e:
        print(f"[ERROR] Lecture image : {e}")
        return []

    preprocess   = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
    ])
    input_tensor = preprocess(raw_img).unsqueeze(0).to(device)

    with torch.no_grad():
        pred = model(input_tensor)[0].cpu().numpy()

    y_grid, x_grid = np.ogrid[:GRID_SIZE, :GRID_SIZE]
    conf_mask = pred[4] > threshold
    if not np.any(conf_mask):
        return []

    scores = pred[4][conf_mask]
    cx     = (x_grid + pred[0])[conf_mask] / GRID_SIZE
    cy     = (y_grid + pred[1])[conf_mask] / GRID_SIZE
    w      = pred[2][conf_mask]
    h      = pred[3][conf_mask]

    raw_boxes  = np.stack([cx - w/2, cy - h/2, cx + w/2, cy + h/2], axis=1)
    raw_scores = scores.astype(float)

    kept = nms(
        torch.tensor(raw_boxes,  dtype=torch.float32),
        torch.tensor(raw_scores, dtype=torch.float32)
    )

    return [{'box': raw_boxes[i].tolist(), 'score': float(raw_scores[i])} for i in kept]