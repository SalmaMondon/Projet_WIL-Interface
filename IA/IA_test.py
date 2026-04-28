import torch
import torch.nn as nn
from torch.optim import Adam
from torch.optim.lr_scheduler import ReduceLROnPlateau
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
import os
from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import cv2

# ============================================================
# CONFIGURATION
# ============================================================
BASE_PATH      = 'IA/Car.v1i.yolov8'
MODEL_PATH     = 'IA/drone_car_model.pth'
GRID_SIZE      = 32
IMG_SIZE       = 256
BATCH_SIZE     = 8
EPOCHS         = 0
LEARNING_RATE  = 1e-3
NMS_THRESHOLD  = 0.4   # Max IoU between two kept boxes
CONF_THRESHOLD = 0.3   # Minimum confidence score

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Running on: {str(device).upper()}")


# ============================================================
# DATASET
# ============================================================
class YoloV8AerialDataset(Dataset):
    def __init__(self, img_dir, label_dir, grid_size=GRID_SIZE):
        self.img_dir   = img_dir
        self.label_dir = label_dir
        self.grid_size = grid_size
        self.img_names = [f for f in os.listdir(img_dir) if f.endswith(('.jpg', '.png', '.jpeg'))]
        self.transform = transforms.Compose([
            transforms.Resize((IMG_SIZE, IMG_SIZE)),
            transforms.ToTensor(),
        ])

    def __len__(self):
        return len(self.img_names)

    def __getitem__(self, idx):
        img_path   = os.path.join(self.img_dir, self.img_names[idx])
        label_path = os.path.join(self.label_dir, os.path.splitext(self.img_names[idx])[0] + ".txt")

        img    = Image.open(img_path).convert("RGB")
        img    = self.transform(img)
        target = torch.zeros(5, self.grid_size, self.grid_size)

        if os.path.exists(label_path):
            with open(label_path, 'r') as f:
                for line in f:
                    parts = line.split()
                    if len(parts) < 5:
                        continue
                    cx, cy, w, h = map(float, parts[1:5])

                    cell_x = min(int(cx * self.grid_size), self.grid_size - 1)
                    cell_y = min(int(cy * self.grid_size), self.grid_size - 1)
                    off_x  = cx * self.grid_size - cell_x
                    off_y  = cy * self.grid_size - cell_y

                    if target[4, cell_y, cell_x] == 0:
                        target[0, cell_y, cell_x] = off_x
                        target[1, cell_y, cell_x] = off_y
                        target[2, cell_y, cell_x] = w
                        target[3, cell_y, cell_x] = h
                        target[4, cell_y, cell_x] = 1

        return img, target


# ============================================================
# ARCHITECTURE — DroneNet (encoder-decoder + lightweight FPN)
#
#   256x256 → c1(32) → 128 → c2(64) → 64 → c3(128) → 32 (skip p3)
#           → c4(256) → 16 → c5(256) → 16
#   Decoder : 16 → upsample → 32 + p3 → fusion → head (5 channels)
# ============================================================
class ConvBlock(nn.Module):
    """Conv 3x3 + BN + ReLU, with optional MaxPool."""
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
        # Encoder
        self.c1 = ConvBlock(3,   32,  pool=True)
        self.c2 = ConvBlock(32,  64,  pool=True)
        self.c3 = ConvBlock(64,  128, pool=True)  # → skip p3 (32x32)
        self.c4 = ConvBlock(128, 256, pool=True)
        self.c5 = ConvBlock(256, 256, pool=False) # global context (16x16)
        # FPN decoder
        self.lateral = nn.Conv2d(256, 128, kernel_size=1)
        self.fusion  = ConvBlock(256, 128)
        # Detection head
        self.head = nn.Conv2d(128, 5, kernel_size=1)

    def forward(self, x):
        x  = self.c1(x)
        x  = self.c2(x)
        p3 = self.c3(x)
        x  = self.c4(p3)
        x  = self.c5(x)

        x = self.lateral(x)
        x = nn.functional.interpolate(x, scale_factor=2, mode='nearest')
        x = torch.cat([x, p3], dim=1)
        x = self.fusion(x)

        return torch.sigmoid(self.head(x))  # (B, 5, 32, 32)


# ============================================================
# LOSS — CIoU
# Better than MSE: penalizes overlap, center distance,
# and aspect ratio consistency simultaneously.
# ============================================================
def ciou_loss(pred_boxes, target_boxes, eps=1e-7):
    """CIoU loss on normalized boxes [cx, cy, w, h] ∈ [0,1]. Input shape: (N, 4)."""
    def to_xyxy(b):
        return torch.stack([
            b[:, 0] - b[:, 2] / 2,
            b[:, 1] - b[:, 3] / 2,
            b[:, 0] + b[:, 2] / 2,
            b[:, 1] + b[:, 3] / 2,
        ], dim=1)

    p = to_xyxy(pred_boxes)
    t = to_xyxy(target_boxes)

    inter_area = (
        (torch.min(p[:, 2], t[:, 2]) - torch.max(p[:, 0], t[:, 0])).clamp(0) *
        (torch.min(p[:, 3], t[:, 3]) - torch.max(p[:, 1], t[:, 1])).clamp(0)
    )
    area_p = (p[:, 2] - p[:, 0]) * (p[:, 3] - p[:, 1])
    area_t = (t[:, 2] - t[:, 0]) * (t[:, 3] - t[:, 1])
    iou    = inter_area / (area_p + area_t - inter_area + eps)

    # Enclosing box
    enc_x1 = torch.min(p[:, 0], t[:, 0])
    enc_y1 = torch.min(p[:, 1], t[:, 1])
    enc_x2 = torch.max(p[:, 2], t[:, 2])
    enc_y2 = torch.max(p[:, 3], t[:, 3])
    c2 = (enc_x2 - enc_x1) ** 2 + (enc_y2 - enc_y1) ** 2 + eps

    # Center distance
    cx_p = (p[:, 0] + p[:, 2]) / 2
    cy_p = (p[:, 1] + p[:, 3]) / 2
    cx_t = (t[:, 0] + t[:, 2]) / 2
    cy_t = (t[:, 1] + t[:, 3]) / 2
    d2   = (cx_p - cx_t) ** 2 + (cy_p - cy_t) ** 2

    # Aspect ratio consistency
    v = (4 / (torch.pi ** 2)) * (
        torch.atan(target_boxes[:, 2] / (target_boxes[:, 3] + eps)) -
        torch.atan(pred_boxes[:, 2]   / (pred_boxes[:, 3]   + eps))
    ) ** 2
    with torch.no_grad():
        alpha = v / (1 - iou + v + eps)

    return 1 - (iou - d2 / c2 - alpha * v)


def yolo_loss(pred, target):
    mse        = nn.MSELoss(reduction='sum')
    obj_mask   = target[:, 4:5, :, :]
    noobj_mask = 1 - obj_mask

    loss_conf_obj   = mse(pred[:, 4:5] * obj_mask,   target[:, 4:5] * obj_mask)
    loss_conf_noobj = mse(pred[:, 4:5] * noobj_mask, target[:, 4:5] * noobj_mask)

    obj_indices = obj_mask[:, 0].nonzero(as_tuple=False)
    if obj_indices.shape[0] > 0:
        b_idx, y_idx, x_idx = obj_indices[:, 0], obj_indices[:, 1], obj_indices[:, 2]

        pred_coord = pred[b_idx, :4, y_idx, x_idx]
        tgt_coord  = target[b_idx, :4, y_idx, x_idx]

        def to_abs(coords, xi, yi):
            cx = (xi.float() + coords[:, 0]) / GRID_SIZE
            cy = (yi.float() + coords[:, 1]) / GRID_SIZE
            return torch.stack([cx, cy, coords[:, 2], coords[:, 3]], dim=1)

        loss_coord = ciou_loss(to_abs(pred_coord, x_idx, y_idx),
                               to_abs(tgt_coord,  x_idx, y_idx)).sum()
    else:
        loss_coord = torch.tensor(0.0, device=pred.device)

    return 5.0 * loss_coord + loss_conf_obj + 0.5 * loss_conf_noobj


# ============================================================
# NMS — Non-Maximum Suppression
# Sort by confidence, keep the best box and discard all others
# with IoU above NMS_THRESHOLD.
# ============================================================
def compute_iou(box, boxes):
    """IoU between one box (4,) and a set of boxes (N, 4) in xyxy format."""
    inter = (
        (torch.min(box[2], boxes[:, 2]) - torch.max(box[0], boxes[:, 0])).clamp(0) *
        (torch.min(box[3], boxes[:, 3]) - torch.max(box[1], boxes[:, 1])).clamp(0)
    )
    area_box   = (box[2]      - box[0])      * (box[3]      - box[1])
    area_boxes = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    return inter / (area_box + area_boxes - inter + 1e-7)


def nms(boxes, scores, iou_threshold=NMS_THRESHOLD):
    """Returns indices of boxes kept after NMS."""
    order = scores.argsort(descending=True)
    kept  = []
    while order.numel() > 0:
        i = order[0].item()
        kept.append(i)
        if order.numel() == 1:
            break
        rest  = order[1:]
        order = rest[compute_iou(boxes[i], boxes[rest]) < iou_threshold]
    return kept


# ============================================================
# MODEL
# ============================================================
model = DroneNet().to(device)


# ============================================================
# TRAINING
# ============================================================
def train():
    train_loader = DataLoader(
        YoloV8AerialDataset(f'{BASE_PATH}/train/images', f'{BASE_PATH}/train/labels'),
        batch_size=BATCH_SIZE, shuffle=True
    )

    optimizer = Adam(model.parameters(), lr=LEARNING_RATE)
    scheduler = ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=3)

    if os.path.exists(MODEL_PATH):
        model.load_state_dict(torch.load(MODEL_PATH, map_location=device))
        print(f"--- Model loaded from {MODEL_PATH} ---")
    else:
        print("--- No saved model found, starting from scratch ---")

    if EPOCHS > 0:
        print(f"Starting training for {EPOCHS} epochs...")
        for epoch in range(EPOCHS):
            model.train()
            total_loss = 0
            for batch_idx, (imgs, targets) in enumerate(train_loader):
                imgs, targets = imgs.to(device), targets.to(device)
                optimizer.zero_grad()
                loss = yolo_loss(model(imgs), targets)
                loss.backward()
                optimizer.step()
                total_loss += loss.item()
                if batch_idx % 10 == 0:
                    print(f"  Epoch {epoch+1} | Batch {batch_idx}/{len(train_loader)} | Loss: {loss.item():.4f}")

            avg_loss = total_loss / len(train_loader)
            scheduler.step(avg_loss)
            torch.save(model.state_dict(), MODEL_PATH)
            print(f"--- Epoch {epoch+1} | Avg loss: {avg_loss:.4f} | LR: {optimizer.param_groups[0]['lr']:.2e} | Saved ---")


# ============================================================
# DISPLAY
# ============================================================
def plot_prediction(img_tensor, pred, threshold=CONF_THRESHOLD):
    """Display the image with detection boxes after NMS."""
    pred_np    = pred.numpy()
    raw_boxes  = []
    raw_scores = []

    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            conf = pred_np[4, y, x]
            if conf > threshold:
                cx = (x + pred_np[0, y, x]) / GRID_SIZE * IMG_SIZE
                cy = (y + pred_np[1, y, x]) / GRID_SIZE * IMG_SIZE
                w  = pred_np[2, y, x] * IMG_SIZE
                h  = pred_np[3, y, x] * IMG_SIZE
                raw_boxes.append([cx - w/2, cy - h/2, cx + w/2, cy + h/2])
                raw_scores.append(conf)

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.imshow(img_tensor.permute(1, 2, 0).numpy())

    if raw_boxes:
        kept = nms(torch.tensor(raw_boxes,  dtype=torch.float32),
                   torch.tensor(raw_scores, dtype=torch.float32))
        for i in kept:
            x1, y1, x2, y2 = raw_boxes[i]
            ax.add_patch(patches.Rectangle(
                (x1, y1), x2 - x1, y2 - y1,
                linewidth=2, edgecolor='r', facecolor='none'
            ))
            ax.text(x1, y1 - 3, f"{raw_scores[i]:.2f}",
                    color='yellow', fontsize=7, fontweight='bold')
        ax.set_title(f"Cars detected (after NMS): {len(kept)}")
    else:
        ax.set_title("No detection above threshold")

    ax.axis('off')
    plt.tight_layout()
    plt.show()


# ============================================================
# DETECTION
# ============================================================
def detect(image_input, threshold=CONF_THRESHOLD):
    """
    Detect cars in an image and return boxes after NMS.
    Accepts: file path (str), NumPy array (BGR), or PIL Image.
    Returns: [{'box': [x1, y1, x2, y2], 'score': float}, ...]
    """
    try:
        if isinstance(image_input, str):
            raw_img = Image.open(image_input).convert("RGB")
        elif isinstance(image_input, np.ndarray):
            raw_img = Image.fromarray(cv2.cvtColor(image_input, cv2.COLOR_BGR2RGB))
        elif hasattr(image_input, 'convert'):
            raw_img = image_input.convert("RGB")
        else:
            raise ValueError(f"Unsupported image format: {type(image_input)}")
    except Exception as e:
        print(f"[ERROR] Failed to read image: {e}")
        return []

    preprocess   = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
    ])
    input_tensor = preprocess(raw_img).unsqueeze(0).to(device)

    model.eval()
    with torch.no_grad():
        pred = model(input_tensor)[0].cpu().numpy()

    y_grid, x_grid = np.ogrid[:GRID_SIZE, :GRID_SIZE]
    conf_mask = pred[4] > threshold
    if not np.any(conf_mask):
        return []

    scores = pred[4][conf_mask]
    cx = (x_grid + pred[0])[conf_mask] / GRID_SIZE * IMG_SIZE
    cy = (y_grid + pred[1])[conf_mask] / GRID_SIZE * IMG_SIZE
    w  = pred[2][conf_mask] * IMG_SIZE
    h  = pred[3][conf_mask] * IMG_SIZE

    raw_boxes  = np.stack([cx - w/2, cy - h/2, cx + w/2, cy + h/2], axis=1)
    raw_scores = scores.astype(float)

    kept_indices = nms(
        torch.tensor(raw_boxes,  dtype=torch.float32),
        torch.tensor(raw_scores, dtype=torch.float32)
    )

    return [{'box': raw_boxes[i].tolist(), 'score': float(raw_scores[i])} for i in kept_indices]


# ============================================================
# DEBUG
# ============================================================
# train()

# img_tensor = transforms.Compose([
#     transforms.Resize((IMG_SIZE, IMG_SIZE)),
#     transforms.ToTensor(),
# ])(Image.open('IA/carviewalive.jpg').convert("RGB"))

# model.eval()
# with torch.no_grad():
#     pred = model(img_tensor.unsqueeze(0).to(device))[0].cpu()

# plot_prediction(img_tensor, pred)