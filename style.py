from PyQt6.QtWidgets import QGraphicsDropShadowEffect
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QCursor
from PyQt6.QtCore import Qt

# --- CONSTANTES DE STYLE (QSS) ---
# On sort les chaînes de caractères pour ne pas encombrer le code
STYLE_GLOBAL = """
    QWidget { background-color: #1e1e2e; color: #cdd6f4; font-family: 'Consolas', 'Courier New', monospace; }
    QPushButton {
        background-color: #34495e; 
        color: white; 
        font-weight: bold; 
        border-radius: 8px; 
        padding: 10px;
        border: none;
    }
    QPushButton:hover { background-color: #2c3e50; }
    QPushButton:pressed, QPushButton[down="true"] { 
        background-color: #1a252f; 
        border: 1px solid #3498db;
        padding-top: 13px;
    }
    QListWidget { background-color: #181825; color: #a6adc8; }
"""

STYLE_BOUTON_IMAGE = """
    QPushButton { background-color: #2ecc71; color: white; font-weight: bold; border-radius: 8px; padding: 10px;}
    QPushButton:hover { background-color: #28b062; }
"""

STYLE_BOUTON_LANGUE = """
    QPushButton { background-color: #960018; color: white; font-weight: bold; border-radius: 8px; padding: 10px;}
    QPushButton:hover { background-color: #850007; }
"""

# --- STYLES DES COMMANDES DE VOL ---

# Modèle de base pour les boutons de pilotage
STYLE_PILOTAGE_BASE = """
    QPushButton {{
        background-color: {couleur};
        color: {texte};
        border: 1px solid {bordure};
        font-weight: bold;
        font-size: 11px;
        {radius}
    }}
    QPushButton:hover {{ background-color: {survol}; }}
    QPushButton:pressed, QPushButton[down="true"] {{ 
        background-color: {pression}; 
        padding-top: 3px; 
    }}
"""

# Déclinaisons spécifiques
STYLE_MONTER = STYLE_PILOTAGE_BASE.format(
    couleur="#00d2ff", texte="#1e1e2e", bordure="#00bcff",
    survol="#70e1ff", pression="#0086a8", 
    radius="border-top-left-radius: 15px; border-top-right-radius: 15px;"
)

STYLE_DESCENDRE = STYLE_PILOTAGE_BASE.format(
    couleur="#3a4df0", texte="white", bordure="#2a3bc0",
    survol="#5d6df5", pression="#1e2a8a", 
    radius="border-bottom-left-radius: 15px; border-bottom-right-radius: 15px;"
)

STYLE_AVANCER = STYLE_PILOTAGE_BASE.format(
    couleur="#34495e", texte="white", bordure="#2c3e50",
    survol="#455d7a", pression="#1a252f", 
    radius="border-top-left-radius: 8px; border-top-right-radius: 8px;"
)

STYLE_RECULER = STYLE_PILOTAGE_BASE.format(
    couleur="#34495e", texte="white", bordure="#2c3e50",
    survol="#455d7a", pression="#1a252f", 
    radius="border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;"
)

STYLE_DROITE = STYLE_PILOTAGE_BASE.format(
    couleur="#34495e", texte="white", bordure="#2c3e50",
    survol="#455d7a", pression="#1a252f", 
    radius="border-top-left-radius: 8px; border-top-right-radius: 8px;"
)

STYLE_GAUCHE = STYLE_PILOTAGE_BASE.format(
    couleur="#34495e", texte="white", bordure="#2c3e50",
    survol="#455d7a", pression="#1a252f", 
    radius="border-bottom-left-radius: 8px; border-bottom-right-radius: 8px;"
)

# --- FONCTIONS DE CRÉATION GRAPHIQUE ---

def creer_curseurs():
    """Crée et retourne les deux curseurs (bleu et rouge)."""
    taille = 32
    
    # --- CURSEUR BLEU ---
    pix_bleu = QPixmap(taille, taille)
    pix_bleu.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix_bleu)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor("#00d2ff"), 2))
    p.drawEllipse(12, 12, 8, 8)
    p.drawLine(16, 4, 16, 10); p.drawLine(16, 22, 16, 28)
    p.drawLine(4, 16, 10, 16); p.drawLine(22, 16, 28, 16)
    p.end()
    
    # --- CURSEUR ROUGE ---
    pix_rouge = QPixmap(taille, taille)
    pix_rouge.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix_rouge)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor("#ff4757"), 3))
    p.drawEllipse(10, 10, 12, 12)
    p.drawLine(16, 2, 16, 12); p.drawLine(16, 20, 16, 30)
    p.drawLine(2, 16, 12, 16); p.drawLine(20, 16, 30, 16)
    p.end()
    
    return QCursor(pix_bleu, 16, 16), QCursor(pix_rouge, 16, 16)

def appliquer_effets_neon(label_compteur, label_altitude):
    """Applique les effets de lueur et assure la transparence du fond."""
    
    # --- Style pour supprimer tout cadre ou fond ---
    style_transparent = "background: transparent; border: none;"
    label_compteur.setStyleSheet(label_compteur.styleSheet() + style_transparent)
    label_altitude.setStyleSheet(label_altitude.styleSheet() + style_transparent)

    # --- Néon Blanc ---
    neon_vert = QGraphicsDropShadowEffect()
    neon_vert.setColor(QColor(255, 255, 255, 255)) # Blanc d'ordre supérieur
    neon_vert.setBlurRadius(25) # Rayon du flou pour l'effet halo
    neon_vert.setOffset(0, 0)   # 0,0 pour que l'ombre soit centrée derrière le texte
    label_compteur.setGraphicsEffect(neon_vert)
    
    # --- Néon Bleu ---
    neon_bleu = QGraphicsDropShadowEffect()
    neon_bleu.setColor(QColor(137, 180, 250, 200)) # Bleu ciel
    neon_bleu.setBlurRadius(20)
    neon_bleu.setOffset(0, 0)
    label_altitude.setGraphicsEffect(neon_bleu)