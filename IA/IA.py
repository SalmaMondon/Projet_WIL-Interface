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

# ----------------------------
# CONFIGURATION
# ----------------------------
BASE_PATH = 'Car.v1i.yolov8'
MODEL_PATH = 'drone_car_model.pth'
GRID_SIZE = 32
IMG_SIZE = 256
BATCH_SIZE = 8
EPOCHS = 0
LEARNING_RATE = 1e-3
NMS_THRESHOLD = 0.4   # IoU max entre deux boîtes gardées
CONF_THRESHOLD = 0.3  # Seuil de confiance minimal

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Exécution sur : {str(device).upper()}")

# ----------------------------
# DATASET YOLOv8 (inchangé)
# ----------------------------
class YoloV8AerialDataset(Dataset):
    def __init__(self, img_dir, label_dir, grid_size=GRID_SIZE):
        self.img_dir = img_dir
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
        img_path = os.path.join(self.img_dir, self.img_names[idx])
        label_path = os.path.join(self.label_dir, os.path.splitext(self.img_names[idx])[0] + ".txt")

        img = Image.open(img_path).convert("RGB")
        img = self.transform(img)

        target = torch.zeros(5, self.grid_size, self.grid_size)

        if os.path.exists(label_path):
            with open(label_path, 'r') as f:
                for line in f:
                    parts = line.split()
                    if len(parts) < 5: continue
                    cx, cy, w, h = map(float, parts[1:5])

                    cell_x = int(cx * self.grid_size)
                    cell_y = int(cy * self.grid_size)
                    cell_x = min(cell_x, self.grid_size - 1)
                    cell_y = min(cell_y, self.grid_size - 1)

                    off_x = cx * self.grid_size - cell_x
                    off_y = cy * self.grid_size - cell_y

                    if target[4, cell_y, cell_x] == 0:
                        target[0, cell_y, cell_x] = off_x
                        target[1, cell_y, cell_x] = off_y
                        target[2, cell_y, cell_x] = w
                        target[3, cell_y, cell_x] = h
                        target[4, cell_y, cell_x] = 1
        return img, target


# ----------------------------
# ARCHITECTURE AMÉLIORÉE
# Ajouts :
#   - Réseau plus profond (5 blocs conv au lieu de 3)
#   - Skip connections style FPN : fusionne features fines (32x32)
#     avec features sémantiques (8x8 upsamplées) pour mieux
#     détecter les petits objets vus du ciel
# ----------------------------
class ConvBlock(nn.Module):
    """Conv 3x3 + BN + ReLU, optionnellement suivi d'un MaxPool."""
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
    """
    Backbone encodeur-décodeur léger avec fusion multi-échelle (FPN simplifié).

    Flux :
        256x256 → c1(32) → pool → 128x128
                → c2(64) → pool → 64x64
                → c3(128) → pool → 32x32  ← skip p3
                → c4(256) → pool → 16x16
                → c5(256)        → 16x16  (features profondes)
        
        Décodeur :
                16x16 → upsample → 32x32 + p3  → fusion → 32x32
                      → tête de détection (5 canaux)
    """
    def __init__(self):
        super().__init__()

        # --- Encodeur ---
        self.c1 = ConvBlock(3,   32,  pool=True)   # → 128
        self.c2 = ConvBlock(32,  64,  pool=True)   # → 64
        self.c3 = ConvBlock(64,  128, pool=True)   # → 32  (skip)
        self.c4 = ConvBlock(128, 256, pool=True)   # → 16
        self.c5 = ConvBlock(256, 256, pool=False)  # → 16  (contexte)

        # --- Décodeur FPN ---
        # Réduit les features profondes avant fusion
        self.lateral = nn.Conv2d(256, 128, kernel_size=1)
        # Après concat (128 deep + 128 skip) → 128 canaux
        self.fusion  = ConvBlock(256, 128)

        # --- Tête de détection ---
        self.head = nn.Conv2d(128, 5, kernel_size=1)

    def forward(self, x):
        x = self.c1(x)
        x = self.c2(x)
        p3 = self.c3(x)   # features à 32x32 (détails fins)
        x  = self.c4(p3)
        x  = self.c5(x)   # features à 16x16 (contexte global)

        # Remonter à 32x32 et fusionner avec le skip
        x = self.lateral(x)
        x = nn.functional.interpolate(x, scale_factor=2, mode='nearest')
        x = torch.cat([x, p3], dim=1)  # (256, 32, 32)
        x = self.fusion(x)             # (128, 32, 32)

        return torch.sigmoid(self.head(x))  # (5, 32, 32)


# ----------------------------
# LOSS CIoU
# Pourquoi CIoU plutôt que MSE ?
#   - MSE pénalise pareil une grande et une petite erreur absolue
#   - CIoU mesure le chevauchement réel des boîtes + pénalise
#     la distance entre centres + le ratio d'aspect
#   → entraînement bien plus stable et précis
# ----------------------------
def ciou_loss(pred_boxes, target_boxes, eps=1e-7):
    """
    CIoU loss sur les boîtes normalisées [cx, cy, w, h] ∈ [0,1].
    Les deux tenseurs sont de forme (N, 4).
    """
    # Conversion cx,cy,w,h → x1,y1,x2,y2
    def to_xyxy(b):
        return torch.stack([
            b[:, 0] - b[:, 2] / 2,
            b[:, 1] - b[:, 3] / 2,
            b[:, 0] + b[:, 2] / 2,
            b[:, 1] + b[:, 3] / 2,
        ], dim=1)

    p = to_xyxy(pred_boxes)
    t = to_xyxy(target_boxes)

    # Aire d'intersection
    inter_x1 = torch.max(p[:, 0], t[:, 0])
    inter_y1 = torch.max(p[:, 1], t[:, 1])
    inter_x2 = torch.min(p[:, 2], t[:, 2])
    inter_y2 = torch.min(p[:, 3], t[:, 3])
    inter_area = (inter_x2 - inter_x1).clamp(0) * (inter_y2 - inter_y1).clamp(0)

    # Aires individuelles
    area_p = (p[:, 2] - p[:, 0]) * (p[:, 3] - p[:, 1])
    area_t = (t[:, 2] - t[:, 0]) * (t[:, 3] - t[:, 1])

    # IoU
    union = area_p + area_t - inter_area + eps
    iou = inter_area / union

    # Boîte englobante (pour DIoU/CIoU)
    enc_x1 = torch.min(p[:, 0], t[:, 0])
    enc_y1 = torch.min(p[:, 1], t[:, 1])
    enc_x2 = torch.max(p[:, 2], t[:, 2])
    enc_y2 = torch.max(p[:, 3], t[:, 3])
    c2 = (enc_x2 - enc_x1) ** 2 + (enc_y2 - enc_y1) ** 2 + eps

    # Distance entre centres (DIoU)
    cx_p = (p[:, 0] + p[:, 2]) / 2
    cy_p = (p[:, 1] + p[:, 3]) / 2
    cx_t = (t[:, 0] + t[:, 2]) / 2
    cy_t = (t[:, 1] + t[:, 3]) / 2
    d2 = (cx_p - cx_t) ** 2 + (cy_p - cy_t) ** 2

    # Terme de cohérence du ratio d'aspect (v)
    v = (4 / (torch.pi ** 2)) * (
        torch.atan(target_boxes[:, 2] / (target_boxes[:, 3] + eps)) -
        torch.atan(pred_boxes[:, 2]   / (pred_boxes[:, 3]   + eps))
    ) ** 2
    with torch.no_grad():
        alpha = v / (1 - iou + v + eps)

    ciou = iou - d2 / c2 - alpha * v
    return 1 - ciou  # perte (plus bas = mieux)


def yolo_loss(pred, target):
    mse = nn.MSELoss(reduction='sum')
    obj_mask  = target[:, 4:5, :, :]   # (B,1,G,G) : 1 là où il y a un objet
    noobj_mask = 1 - obj_mask

    # --- Perte de confiance ---
    loss_conf_obj   = mse(pred[:, 4:5] * obj_mask,   target[:, 4:5] * obj_mask)
    loss_conf_noobj = mse(pred[:, 4:5] * noobj_mask, target[:, 4:5] * noobj_mask)

    # --- Perte de localisation CIoU (uniquement sur les cellules avec objet) ---
    # Récupère les indices des cellules positives
    obj_indices = obj_mask[:, 0].nonzero(as_tuple=False)  # (K, 3) : batch, y, x

    if obj_indices.shape[0] > 0:
        b_idx = obj_indices[:, 0]
        y_idx = obj_indices[:, 1]
        x_idx = obj_indices[:, 2]

        pred_coord = pred[b_idx, :4, y_idx, x_idx]     # (K, 4) : off_x, off_y, w, h
        tgt_coord  = target[b_idx, :4, y_idx, x_idx]

        # Reconstruire cx,cy absolus en [0,1] pour CIoU
        gs = GRID_SIZE
        def to_abs(coords, xi, yi):
            cx = (xi.float() + coords[:, 0]) / gs
            cy = (yi.float() + coords[:, 1]) / gs
            return torch.stack([cx, cy, coords[:, 2], coords[:, 3]], dim=1)

        pred_abs = to_abs(pred_coord, x_idx, y_idx)
        tgt_abs  = to_abs(tgt_coord,  x_idx, y_idx)

        loss_coord = ciou_loss(pred_abs, tgt_abs).sum()
    else:
        loss_coord = torch.tensor(0.0, device=pred.device)

    return 5.0 * loss_coord + loss_conf_obj + 0.5 * loss_conf_noobj


# ----------------------------
# NMS (Non-Maximum Suppression)
# Supprime les boîtes redondantes qui désignent le même mouton.
# Algorithme :
#   1. Trier les détections par confiance décroissante
#   2. Garder la meilleure, supprimer toutes celles dont l'IoU
#      avec elle dépasse NMS_THRESHOLD
#   3. Répéter sur les boîtes restantes
# ----------------------------
def compute_iou(box, boxes):
    """IoU entre une boîte (4,) et un ensemble (N,4) — format xyxy."""
    inter_x1 = torch.max(box[0], boxes[:, 0])
    inter_y1 = torch.max(box[1], boxes[:, 1])
    inter_x2 = torch.min(box[2], boxes[:, 2])
    inter_y2 = torch.min(box[3], boxes[:, 3])
    inter = (inter_x2 - inter_x1).clamp(0) * (inter_y2 - inter_y1).clamp(0)
    area_box  = (box[2] - box[0]) * (box[3] - box[1])
    area_boxes = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    union = area_box + area_boxes - inter + 1e-7
    return inter / union


def nms(boxes, scores, iou_threshold=NMS_THRESHOLD):
    """
    boxes  : (N, 4) en pixels xyxy
    scores : (N,)   confiances
    Retourne les indices des boîtes conservées.
    """
    order = scores.argsort(descending=True)
    kept = []
    while order.numel() > 0:
        i = order[0].item()
        kept.append(i)
        if order.numel() == 1:
            break
        rest = order[1:]
        ious = compute_iou(boxes[i], boxes[rest])
        order = rest[ious < iou_threshold]
    return kept

model = DroneNet().to(device)

def entrainement():
    # ----------------------------
    # INITIALISATION
    # ----------------------------
    train_ds = YoloV8AerialDataset(f'{BASE_PATH}/train/images', f'{BASE_PATH}/train/labels')
    val_ds   = YoloV8AerialDataset(f'{BASE_PATH}/valid/images', f'{BASE_PATH}/valid/labels')

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
    val_loader   = DataLoader(val_ds,   batch_size=BATCH_SIZE)

    
    optimizer = Adam(model.parameters(), lr=LEARNING_RATE)
    # Réduit le lr par 2 si la loss ne baisse plus pendant 3 époques
    scheduler = ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=3)

    if os.path.exists(MODEL_PATH):
        model.load_state_dict(torch.load(MODEL_PATH, map_location=device))
        print(f"--- Modèle chargé depuis {MODEL_PATH} ---")
    else:
        print("--- Aucun entraînement trouvé. Création d'un nouveau modèle ---")

    # ----------------------------
    # BOUCLE D'ENTRAÎNEMENT
    # ----------------------------
    if EPOCHS > 0:
        print(f"Début de l'entraînement pour {EPOCHS} époques...")
        for epoch in range(EPOCHS):
            model.train()
            total_loss = 0
            for batch_idx, (imgs, targets) in enumerate(train_loader):
                imgs, targets = imgs.to(device), targets.to(device)
                optimizer.zero_grad()
                preds = model(imgs)
                loss = yolo_loss(preds, targets)
                loss.backward()
                optimizer.step()

                total_loss += loss.item()
                if batch_idx % 10 == 0:
                    print(f"Epoch {epoch+1} | Batch {batch_idx}/{len(train_loader)} | Loss: {loss.item():.4f}")

            avg_loss = total_loss / len(train_loader)
            scheduler.step(avg_loss)
            current_lr = optimizer.param_groups[0]['lr']
            torch.save(model.state_dict(), MODEL_PATH)
            print(f"--- Fin Epoch {epoch+1} | Loss Moyenne: {avg_loss:.4f} | LR: {current_lr:.2e} | Sauvegardé ---")


# ----------------------------
# AFFICHAGE AVEC NMS
# ----------------------------
def plot_prediction(img, pred, threshold=CONF_THRESHOLD):
    """Affiche l'image avec les boîtes après NMS."""
    img_np = img.permute(1, 2, 0).numpy()
    pred_np = pred.numpy()

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
                x1, y1 = cx - w / 2, cy - h / 2
                x2, y2 = cx + w / 2, cy + h / 2
                raw_boxes.append([x1, y1, x2, y2])
                raw_scores.append(conf)

    plt.figure(figsize=(8, 8))
    plt.imshow(img_np)
    ax = plt.gca()

    if raw_boxes:
        boxes_t  = torch.tensor(raw_boxes,  dtype=torch.float32)
        scores_t = torch.tensor(raw_scores, dtype=torch.float32)
        kept = nms(boxes_t, scores_t)

        for i in kept:
            x1, y1, x2, y2 = raw_boxes[i]
            rect = patches.Rectangle(
                (x1, y1), x2 - x1, y2 - y1,
                linewidth=2, edgecolor='r', facecolor='none'
            )
            ax.add_patch(rect)
            ax.text(x1, y1 - 3, f"{raw_scores[i]:.2f}",
                    color='yellow', fontsize=7, fontweight='bold')

        plt.title(f"Moutons détectés (après NMS) : {len(kept)}")
    else:
        plt.title("Aucune détection au-dessus du seuil")

    plt.axis('off')
    plt.tight_layout()
    plt.show()


def detect(image_input, threshold=CONF_THRESHOLD):
    """
    Accepte un chemin (str), une PIL Image, ou un numpy array (BGR OpenCV).
    Retourne une liste de dicts : [{'box': [x1,y1,x2,y2], 'score': float}, ...]
    """
    if isinstance(image_input, str):
        raw_img = Image.open(image_input).convert("RGB")
    elif isinstance(image_input, np.ndarray):
        raw_img = Image.fromarray(cv2.cvtColor(image_input, cv2.COLOR_BGR2RGB))
    else:
        raw_img = image_input.convert("RGB")

    preprocess = transforms.Compose([
        transforms.Resize((IMG_SIZE, IMG_SIZE)),
        transforms.ToTensor(),
    ])

    input_tensor = preprocess(raw_img).unsqueeze(0).to(device)
    model.eval()
    with torch.no_grad():
        pred = model(input_tensor)[0].cpu().numpy()

    # Récupère les boxes brutes au-dessus du seuil
    raw_boxes, raw_scores = [], []
    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            conf = pred[4, y, x]
            if conf > threshold:
                cx = (x + pred[0, y, x]) / GRID_SIZE * IMG_SIZE
                cy = (y + pred[1, y, x]) / GRID_SIZE * IMG_SIZE
                w  = pred[2, y, x] * IMG_SIZE
                h  = pred[3, y, x] * IMG_SIZE
                raw_boxes.append([cx - w/2, cy - h/2, cx + w/2, cy + h/2])
                raw_scores.append(float(conf))

    if not raw_boxes:
        return []

    boxes_t  = torch.tensor(raw_boxes,  dtype=torch.float32)
    scores_t = torch.tensor(raw_scores, dtype=torch.float32)
    kept = nms(boxes_t, scores_t)

    return [{'box': raw_boxes[i], 'score': raw_scores[i]} for i in kept]