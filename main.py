import os
import sys

# Add Torch DLL path for Windows
torch_lib_path = os.path.join(os.getenv('LOCALAPPDATA'),
    r"Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\site-packages\torch\lib")
if os.path.exists(torch_lib_path):
    os.add_dll_directory(torch_lib_path)

import ctypes
import style
from IA.main_IA import run_pipeline
from database_manager import DatabaseManager
from config_manager import charger_configuration, sauvegarder_configuration
from utils import FiltreCurseurLockOn, IAWorker, resource_path
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                              QPushButton, QLabel, QProgressBar, QFileDialog,
                              QComboBox, QGridLayout, QListWidget)
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QFont, QIcon, QMovie
from PyQt6.QtCore import QRectF, Qt, QRect, QVariantAnimation
from random import randint

# Windows taskbar icon fix
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
        'mon_projet.drone_wil.station.v0.1')
except Exception:
    pass


class StationControleWIL(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WIL")
        self.setWindowIcon(QIcon(resource_path("assets/logo.ico")))
        self.resize(1000, 600)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self.db = DatabaseManager("projet_wil.db")

        self.image_originale    = QPixmap()
        self.objets_detectes    = []
        self.afficher_boxes     = True
        self.langue             = charger_configuration()
        self.chemin_image_actuelle = ""
        self.message_overlay    = "Choisissez une image"

        # Loading spinner
        self.loader = QLabel(self)
        self.movie  = QMovie("assets/chargement.gif")
        self.loader.setFixedSize(100, 100)
        self.movie.setScaledSize(self.loader.size())
        self.loader.setMovie(self.movie)
        self.loader.hide()

        self.init_ui()
        self.appliquer_style_sombre()
        self.appliquer_textes_langue()

        self.curseur_bleu, self.curseur_rouge = style.creer_curseurs()
        self.filtre_lockon = FiltreCurseurLockOn(self.curseur_rouge, self)
        self.appliquer_curseur_perso()
        self.configurer_interactions_souris()

        for bouton in self.findChildren(QPushButton):
            bouton.installEventFilter(self.filtre_lockon)
        self.combo_objets.installEventFilter(self.filtre_lockon)
        self.liste_historique.installEventFilter(self.filtre_lockon)

        if self.langue:
            self.langue = not self.langue
            self.changer_langue()

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)


    # =========================================================
    # UI CONSTRUCTION
    # =========================================================
    def init_ui(self):
        layout_global = QHBoxLayout()

        # ----- LEFT : TELEMETRY -----
        layout_telemetrie = QVBoxLayout()

        self.label_logo = QLabel()
        pixmap_logo = QPixmap(resource_path("assets/logo_wil_quedar.png"))
        self.label_logo.setPixmap(pixmap_logo.scaled(
            200, 200, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        self.label_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_telemetrie.addWidget(self.label_logo)

        self.label_titre = QLabel("\n DONNÉES DE BORD")
        self.label_titre.setStyleSheet("font-weight: bold; font-size: 16px; color: #3498db;")
        layout_telemetrie.addWidget(self.label_titre)

        self.label_batterie = QLabel("Batterie :")
        layout_telemetrie.addWidget(self.label_batterie)

        layout_batterie_container = QHBoxLayout()
        self.barre_batterie = QProgressBar()
        self.barre_batterie.setValue(100)
        self.barre_batterie.setFixedSize(150, 40)
        self.barre_batterie.setTextVisible(False)
        self.barre_batterie.setStyleSheet("""
            QProgressBar {
                border: 3px solid #7f8c8d; border-radius: 5px;
                background-color: #2c3e50; margin-right: 10px;
            }
            QProgressBar::chunk { background-color: #2ecc71; width: 10px; margin: 2px; }
        """)
        self.embout_batterie = QLabel()
        self.embout_batterie.setFixedSize(8, 20)
        self.embout_batterie.setStyleSheet("background-color: #7f8c8d; border-radius: 2px;")
        self.pourcentage_batterie = QLabel(f"{self.barre_batterie.value()}%")
        self.pourcentage_batterie.setStyleSheet("color: white; font-weight: bold; margin-left: 5px;")
        layout_batterie_container.addWidget(self.barre_batterie)
        layout_batterie_container.addWidget(self.embout_batterie)
        layout_batterie_container.addWidget(self.pourcentage_batterie)
        layout_batterie_container.addStretch()
        layout_telemetrie.addLayout(layout_batterie_container)

        self.label_altitude = QLabel("Altitude : 0.0 m")
        self.label_altitude.setStyleSheet(
            "font-size: 20px; padding: 10px; background: #ecf0f1; border-radius: 5px;")
        layout_telemetrie.addWidget(self.label_altitude)

        self.label_statut = QLabel("STATUT : DÉCONNECTÉ")
        self.label_statut.setStyleSheet(
            "color: red; font-weight: bold; font-family: 'Consolas', 'Courier New', monospace;")
        layout_telemetrie.addWidget(self.label_statut)

        self.label_archive = QLabel("")
        self.label_archive.setStyleSheet("color: #2980b9; font-weight: bold;")
        layout_telemetrie.addWidget(self.label_archive)

        # D-Pad
        self.label_pilotage = QLabel("\n COMMANDES DE VOL")
        self.label_pilotage.setStyleSheet("font-weight: bold; color: #3498db;")
        layout_telemetrie.addWidget(self.label_pilotage)

        layout_fleches = QGridLayout()
        layout_fleches.setSpacing(5)

        self.btn_up       = QPushButton("▲")
        self.btn_down     = QPushButton("▼")
        self.btn_left     = QPushButton("◀")
        self.btn_right    = QPushButton("▶")
        self.btn_monter   = QPushButton("▲")
        self.btn_descendre = QPushButton("▼")
        self.btn_monter.setFixedSize(50, 25)
        self.btn_descendre.setFixedSize(50, 25)

        style_btn = "font-size: 18px; font-weight: bold; width: 45px; height: 45px; padding: 0px;"
        for btn in [self.btn_up, self.btn_down, self.btn_left, self.btn_right,
                    self.btn_descendre, self.btn_monter]:
            btn.setStyleSheet(style_btn)
        style_v = "font-size: 16px; font-weight: bold; width: 45px; height: 35px; padding: 0px;"
        self.btn_monter.setStyleSheet(
            style_v + "background-color: #e67e22; border-top-left-radius: 20px; border-top-right-radius: 20px;")
        self.btn_descendre.setStyleSheet(
            style_v + "background-color: #d35400; border-bottom-left-radius: 20px; border-bottom-right-radius: 20px;")

        layout_fleches.addWidget(self.btn_up,    0, 1)
        layout_fleches.addWidget(self.btn_left,  1, 0)
        layout_fleches.addWidget(self.btn_right, 1, 2)
        layout_fleches.addWidget(self.btn_down,  2, 1)

        layout_central = QVBoxLayout()
        layout_central.setSpacing(0)
        layout_central.setContentsMargins(0, 0, 0, 0)
        layout_central.addWidget(self.btn_monter)
        layout_central.addWidget(self.btn_descendre)
        layout_fleches.addLayout(layout_central, 1, 1, Qt.AlignmentFlag.AlignCenter)
        layout_telemetrie.addLayout(layout_fleches)

        layout_telemetrie.addStretch()
        layout_global.addLayout(layout_telemetrie, stretch=1)

        # History panel
        self.layout_historique = QVBoxLayout()
        self.label_historique  = QLabel("Historique")
        self.layout_historique.addWidget(self.label_historique)
        self.liste_historique = QListWidget()
        self.liste_historique.itemClicked.connect(self.charger_depuis_historique)
        self.layout_historique.addWidget(self.liste_historique)
        self.btn_rapport = QPushButton("Générer un rapport CSV")
        self.btn_rapport.clicked.connect(self.generer_rapport)
        self.layout_historique.addWidget(self.btn_rapport)

        # 1. On ne recrée pas l'objet s'il existe déjà !
        # On vérifie si la combo existe, sinon on la crée
        self.layout_type_objet = QLabel() # Le texte sera mis par appliquer_textes_langue
        layout_telemetrie.addWidget(self.layout_type_objet)
        self.combo_objets = QComboBox()
        self.combo_objets.setStyleSheet("""
            QComboBox { background-color: #34495e; color: white; border-radius: 5px;
                        padding: 5px; font-weight: bold; }
            QComboBox QAbstractItemView { background-color: #1e1e2e; color: white;
                                        selection-background-color: #3498db; }
        """)
        layout_telemetrie.addWidget(self.combo_objets)


        # ----- RIGHT : IMAGE + CONTROLS -----
        layout_droite = QVBoxLayout()

        self.label_compteur = QLabel("Detected objects : 0" if self.langue else "Objets détectés : 0")
        self.label_compteur.setStyleSheet("""
            font-size: 24px; font-weight: bold; color: #ffffff;
            background: rgba(255, 255, 255, 150); border-radius: 10px;
        """)
        self.label_compteur.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_droite.addWidget(self.label_compteur)

        self.canvas = QLabel("Aucune image")
        self.canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas.setMinimumSize(640, 480)
        self.canvas.setStyleSheet("border: 2px solid #2c3e50; background: black; color: white;")
        layout_droite.addWidget(self.canvas, stretch=4)

        layout_commandes = QHBoxLayout()
        self.btn_image   = QPushButton("Choisir une image")
        self.btn_image.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold;")
        self.btn_compter = QPushButton("Compter les objets")
        self.btn_toggle  = QPushButton("Masquer les détections")
        self.btn_langue  = QPushButton("Switch to English")
        self.btn_langue.setStyleSheet("background-color: #960018; color: white; font-weight: bold;")
        layout_commandes.addWidget(self.btn_image)
        layout_commandes.addWidget(self.btn_compter)
        layout_commandes.addWidget(self.btn_toggle)
        layout_commandes.addWidget(self.btn_langue)
        layout_droite.addLayout(layout_commandes)

        layout_global.addLayout(layout_droite, stretch=4)
        layout_global.addLayout(self.layout_historique, stretch=1)

        for bouton in self.findChildren(QPushButton):
            bouton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.liste_historique.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.combo_objets.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self.setLayout(layout_global)
        self.dessiner_tout()

        # Signal connections
        self.btn_image.clicked.connect(self.action_image)
        self.btn_compter.clicked.connect(self.action_compter)
        self.btn_toggle.clicked.connect(self.toggle_overlay)
        self.btn_langue.clicked.connect(self.changer_langue)

        self.btn_up.pressed.connect(lambda: self.piloter("AVANCER"))
        self.btn_up.released.connect(self.reinitialiser_statut)
        self.btn_down.pressed.connect(lambda: self.piloter("RECULER"))
        self.btn_down.released.connect(self.reinitialiser_statut)
        self.btn_left.pressed.connect(lambda: self.piloter("GAUCHE"))
        self.btn_left.released.connect(self.reinitialiser_statut)
        self.btn_right.pressed.connect(lambda: self.piloter("DROITE"))
        self.btn_right.released.connect(self.reinitialiser_statut)
        self.btn_monter.pressed.connect(lambda: self.piloter("MONTER"))
        self.btn_monter.released.connect(self.reinitialiser_statut)
        self.btn_descendre.pressed.connect(lambda: self.piloter("DESCENDRE"))
        self.btn_descendre.released.connect(self.reinitialiser_statut)

        self.appliquer_textes_langue()

    # =========================================================
    # LOGIC
    # =========================================================
    def configurer_interactions_souris(self):
        self.setCursor(self.curseur_bleu)
        self.combo_objets.setCursor(self.curseur_bleu)
        boutons_tactiques = [
            self.btn_monter, self.btn_descendre,
            self.btn_up, self.btn_down, self.btn_right, self.btn_left,
            self.btn_image, self.btn_compter, self.btn_langue,
            self.btn_rapport, self.combo_objets
        ]
        self.combo_objets.view().setCursor(self.curseur_bleu)
        for btn in boutons_tactiques:
            btn.installEventFilter(self.filtre_lockon)


    def animer_altitude(self, nouvelle_valeur):
        try:
            valeur_actuelle = float(
                self.label_altitude.text().split(":")[1].replace("m", "").strip())
        except Exception:
            valeur_actuelle = 0.0
        self.animation = QVariantAnimation(self)
        self.animation.setStartValue(valeur_actuelle)
        self.animation.setEndValue(float(nouvelle_valeur))
        self.animation.setDuration(1000)
        self.animation.valueChanged.connect(self.mettre_a_jour_label_altitude)
        self.animation.start()


    def mettre_a_jour_label_altitude(self, valeur):
        self.label_altitude.setText(f"Altitude : {valeur:.1f} m")


    def mettre_a_jour_batterie(self, valeur):
        self.barre_batterie.setValue(valeur)
        self.pourcentage_batterie.setText(f"{valeur}%")
        if valeur > 50:
            couleur = "#2ecc71"
        elif valeur > 20:
            couleur = "#f39c12"
        else:
            couleur = "#e74c3c"
        self.barre_batterie.setStyleSheet(f"""
            QProgressBar {{ border: 3px solid #7f8c8d; border-radius: 5px;
                            background-color: #2c3e50; margin-right: 10px; }}
            QProgressBar::chunk {{ background-color: {couleur}; width: 10px; margin: 2px; }}
        """)


    def appliquer_style_sombre(self):
        self.setStyleSheet(style.STYLE_GLOBAL)
        self.btn_image.setStyleSheet(style.STYLE_BOUTON_IMAGE)
        self.btn_langue.setStyleSheet(style.STYLE_BOUTON_LANGUE)
        self.btn_monter.setStyleSheet(style.STYLE_MONTER)
        self.btn_descendre.setStyleSheet(style.STYLE_DESCENDRE)
        self.btn_up.setStyleSheet(style.STYLE_AVANCER)
        self.btn_down.setStyleSheet(style.STYLE_RECULER)
        self.btn_right.setStyleSheet(style.STYLE_DROITE)
        self.btn_left.setStyleSheet(style.STYLE_GAUCHE)
        self.canvas.setStyleSheet(
            "border: 2px solid #89b4fa; background: #000000; border-radius: 10px;")
        style.appliquer_effets_neon(self.label_compteur, self.label_altitude)
        self.label_statut.setStyleSheet("color: #e74c3c; font-weight: bold; padding: 10px;")


    def appliquer_textes_langue(self):
        # 1. SAUVEGARDE de l'index actuel (pour ne pas perdre le choix de l'utilisateur)
        current_idx = self.combo_objets.currentIndex()
        
        # 2. MISE À JOUR DES TEXTES GÉNÉRAUX
        if self.langue:
            self.label_titre.setText("\n FLIGHT DATA")
            self.label_batterie.setText("Battery:")
            self.label_pilotage.setText("\n FLIGHT CONTROLS")
            self.label_historique.setText("History")
            self.btn_image.setText("Choose an image")
            self.btn_compter.setText("Count objects")
            self.btn_toggle.setText("Hide detections" if self.afficher_boxes else "Display detections")
            self.btn_langue.setText("Passer en Français")
            self.btn_rapport.setText("Generate CSV report")
            self.layout_type_objet.setText("Object type to detect:")
            self.label_compteur.setText(f"Detected objects: 0")
            
            # Mise à jour des items du menu
            self.combo_objets.blockSignals(True) # Évite de lancer un calcul par erreur
            self.combo_objets.clear()
            self.combo_objets.addItems(["Sheep", "Cars", "Humans", "Buildings"])
            self.combo_objets.blockSignals(False)
        else:
            self.label_titre.setText("\n DONNÉES DE BORD")
            self.label_batterie.setText("Batterie :")
            self.label_pilotage.setText("\n COMMANDES DE VOL")
            self.label_historique.setText("Historique")
            self.btn_image.setText("Choisir une image")
            self.btn_compter.setText("Compter les objets")
            self.btn_toggle.setText("Masquer les détections" if self.afficher_boxes else "Afficher les détections")
            self.btn_langue.setText("Switch to English")
            self.btn_rapport.setText("Générer un rapport CSV")
            self.layout_type_objet.setText("Type d'objet à détecter :")
            self.label_compteur.setText(f"Objets détectés : 0")
            
            # Mise à jour des items du menu
            self.combo_objets.blockSignals(True)
            self.combo_objets.clear()
            self.combo_objets.addItems(["Moutons", "Voitures", "Humains", "Bâtiments"])
            self.combo_objets.blockSignals(False)

        # 3. RESTAURATION de l'index
        # Si c'était le premier lancement, current_idx est -1, donc on force 0
        self.combo_objets.setCurrentIndex(max(0, current_idx))


    def action_image(self):
        chemin_fichier, _ = QFileDialog.getOpenFileName(
            self,
            "Sélectionner la photo du dirigeable",
            "C:/Users/Lenovo/Pictures",
            "Images (*.png *.jpeg *.jpg *.bmp);;Tous les fichiers (*)"
        )
        if chemin_fichier:
            self.message_overlay = ""
            self.chemin_image_actuelle = chemin_fichier
            self.charger_nouvelle_image(chemin_fichier, [])


    def action_compter(self):
        if self.image_originale.isNull() or not self.chemin_image_actuelle:
            self.message_overlay = (
                "ERROR : load a picture first !" if self.langue
                else "ERREUR : Chargez une image d'abord !")
            self.dessiner_tout()
            return

        x = (self.width()  - self.loader.width())  // 2
        y = (self.height() - self.loader.height()) // 2
        self.loader.move(x, y)
        self.loader.show()
        self.loader.raise_()
        self.movie.start()
        self.btn_compter.setEnabled(False)

        self.worker = IAWorker()
        self.worker.finished.connect(self.finaliser_comptage)
        self.worker.error.connect(lambda err: print(f"Erreur IA : {err}"))
        self.worker.start()


    def finaliser_comptage(self, coordonnees_brutes):
        # Stop loader
        self.movie.stop()
        self.loader.hide()
        self.btn_compter.setEnabled(True)

        # Convert (x, y, w, h) tuples → QRect (coordonnées image originale)
        rectangles = []
        for det in coordonnees_brutes:
            x, y, w, h = det
            if w > 0 and h > 0:
                rectangles.append(QRect(x, y, w, h))

        # Display
        nb_trouve   = len(rectangles)
        type_objet  = self.combo_objets.currentText()
        self.charger_nouvelle_image('output/output_image.jpg', rectangles)
        texte = (f"{type_objet} detected: {nb_trouve}" if self.langue
                 else f"{type_objet} détectés : {nb_trouve}")
        self.label_compteur.setText(texte)

        # Altitude + save
        altitude_actuelle = round(randint(10, 50) + (randint(0, 9) / 10), 1)
        self.animer_altitude(altitude_actuelle)
        self.enregistrer_capture(
            self.chemin_image_actuelle, altitude_actuelle, nb_trouve, type_objet)


    def toggle_overlay(self):
        self.afficher_boxes = not self.afficher_boxes
        if self.langue:
            self.btn_toggle.setText(
                "Hide detections" if self.afficher_boxes else "Display detections")
        else:
            self.btn_toggle.setText(
                "Masquer les détections" if self.afficher_boxes else "Afficher les détections")
        self.dessiner_tout()


    def changer_langue(self):
        self.langue = not self.langue
        sauvegarder_configuration(self.langue)
        self.appliquer_textes_langue()
        if self.langue:
            self.label_statut.setText("STATUS : DISCONNECTED")
        else:
            self.label_statut.setText("STATUT : DÉCONNECTÉ")


    def charger_nouvelle_image(self, chemin, coordonnees):
        self.image_originale = QPixmap(chemin)
        if self.image_originale.isNull():
            self.message_overlay = "ERROR" if self.langue else "ERREUR : Fichier introuvable !"
            self.dessiner_tout()
            return

        self.message_overlay = ""

        # Accept QRect, QRectF, or (x,y,w,h) tuples
        if coordonnees and not isinstance(coordonnees[0], (QRect, QRectF)):
            self.objets_detectes = [QRect(x, y, w, h) for (x, y, w, h) in coordonnees]
        else:
            self.objets_detectes = coordonnees if coordonnees else []

        nb = len(self.objets_detectes)
        self.label_compteur.setText(
            f"Detected objects: {nb}" if self.langue else f"Objets détectés : {nb}")
        self.dessiner_tout()


    # =========================================================
    # RENDERING
    # =========================================================
    def dessiner_tout(self):
        # --- CASE 1: STANDBY (RADAR) ---
        if self.image_originale.isNull():
            self.canvas.setScaledContents(True)
            largeur = max(self.canvas.width(), 640)
            hauteur = max(self.canvas.height(), 480)

            fond_veille = QPixmap(largeur, hauteur)
            fond_veille.fill(QColor("#0b0e14"))

            painter = QPainter(fond_veille)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            pen_grille = QPen(QColor(137, 180, 250, 40))
            pen_grille.setWidth(1)
            painter.setPen(pen_grille)
            pas = 40
            for x in range(0, largeur, pas):
                painter.drawLine(x, 0, x, hauteur)
            for y in range(0, hauteur, pas):
                painter.drawLine(0, y, largeur, y)

            centre = fond_veille.rect().center()
            for r in range(100, 600, 100):
                painter.drawEllipse(centre, r, r)

            pixmap_logo = QPixmap(resource_path("assets/logo_wil_quedar_radar.png"))
            if not pixmap_logo.isNull():
                painter.setOpacity(0.2)
                logo_redim = pixmap_logo.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio)
                x_logo = (largeur - logo_redim.width())  // 2
                y_logo = (hauteur - logo_redim.height()) // 2
                painter.drawPixmap(x_logo, y_logo, logo_redim)

            if self.message_overlay:
                painter.setOpacity(1.0)
                police = QFont("Consolas", 18)
                police.setBold(True)
                police.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 110)
                painter.setFont(police)
                couleur = (QColor("#ff5555") if "ERREUR" in self.message_overlay
                           else QColor("#89b4fa"))
                painter.setPen(couleur)
                rect_texte = fond_veille.rect().adjusted(20, 20, -20, -20)
                painter.drawText(
                    rect_texte,
                    Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                    self.message_overlay)

            painter.end()
            self.canvas.setPixmap(fond_veille)
            return

        # --- CASE 2: IMAGE PRESENT ---
        self.canvas.setScaledContents(False)

        # 1. Resize image to canvas (keep aspect ratio)
        pixmap_redim = self.image_originale.scaled(
            self.canvas.width(), self.canvas.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)

        # 2. Scale + centering offset
        scale_x  = pixmap_redim.width()  / self.image_originale.width()
        scale_y  = pixmap_redim.height() / self.image_originale.height()
        offset_x = (self.canvas.width()  - pixmap_redim.width())  // 2
        offset_y = (self.canvas.height() - pixmap_redim.height()) // 2

        # 3. Black canvas = QLabel size
        canvas_pixmap = QPixmap(self.canvas.width(), self.canvas.height())
        canvas_pixmap.fill(QColor("black"))

        # 4. Draw resized image at offset
        painter = QPainter(canvas_pixmap)
        painter.drawPixmap(offset_x, offset_y, pixmap_redim)

        # 5. Draw detection boxes on top
        if self.afficher_boxes and self.objets_detectes:
            painter.setPen(QPen(QColor(255, 50, 50), 3))

            for rect in self.objets_detectes:
                x_f, y_f, w_f, h_f = rect.getRect()
                x = int(x_f * scale_x) + offset_x
                y = int(y_f * scale_y) + offset_y
                w = int(w_f * scale_x)
                h = int(h_f * scale_y)
                t = max(1, int(min(w, h) * 0.25))

                # Corners
                painter.drawLine(x,     y,     x + t,     y)
                painter.drawLine(x,     y,     x,         y + t)
                painter.drawLine(x + w, y,     x + w - t, y)
                painter.drawLine(x + w, y,     x + w,     y + t)
                painter.drawLine(x,     y + h, x + t,     y + h)
                painter.drawLine(x,     y + h, x,         y + h - t)
                painter.drawLine(x + w, y + h, x + w - t, y + h)
                painter.drawLine(x + w, y + h, x + w,     y + h - t)

                # Center dot
                painter.setBrush(QColor(255, 50, 50))
                painter.drawEllipse(x + w//2 - 3, y + h//2 - 3, 6, 6)
                painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.end()
        self.canvas.setPixmap(canvas_pixmap)


    # =========================================================
    # DATA / HISTORY
    # =========================================================
    def enregistrer_capture(self, chemin, altitude, nb, type_objet):
        """Save mission to DB and update history list."""
        h = self.db.sauvegarder_mission(chemin, altitude, nb, type_objet, self.objets_detectes)
        self.liste_historique.addItem(f"[{h}] - {nb} {type_objet} (Alt: {altitude}m)")


    def generer_rapport(self):
        try:
            chemin = self.db.exporter_csv(self.langue)
            texte  = (f"Report generated in {chemin}" if self.langue
                      else f"Rapport généré dans {chemin}")
            self.label_archive.setText(texte)
            self.label_archive.setStyleSheet("color: #2ecc71; font-weight: bold;")
        except Exception as e:
            self.label_archive.setText("Erreur export CSV")
            print(e)


    def charger_depuis_historique(self, item):
        texte_complet = item.text()
        try:
            horodatage = texte_complet.split(']')[0].replace('[', '')
            resultat   = self.db.recuperer_mission_par_horodatage(horodatage)
            if resultat:
                chemin, nb, type_obj, chaine_coords, altitude = resultat
                nouvelles_coords = []
                if chaine_coords:
                    for bloc in chaine_coords.split(';'):
                        if bloc:
                            x, y, w, h = map(int, bloc.split(','))
                            nouvelles_coords.append(QRect(x, y, w, h))
                self.chemin_image_actuelle = chemin
                self.charger_nouvelle_image(chemin, nouvelles_coords)
                self.animer_altitude(altitude)
                msg = (f"Archive: {horodatage} ({nb} {type_obj})" if self.langue
                       else f"Archive : {horodatage} ({nb} {type_obj})")
                self.label_archive.setText(msg)
                self.label_archive.setStyleSheet("color: #2980b9; font-weight: bold;")
        except Exception as e:
            print(f"Erreur historique (UI) : {e}")


    # =========================================================
    # KEYBOARD / PILOTING
    # =========================================================
    def keyPressEvent(self, event):
        if event.isAutoRepeat():
            return
        touche = event.key()
        if touche == Qt.Key.Key_Up:
            self.btn_up.setDown(True);    self.piloter("AVANCER")
        elif touche == Qt.Key.Key_Down:
            self.btn_down.setDown(True);  self.piloter("RECULER")
        elif touche == Qt.Key.Key_Left:
            self.btn_left.setDown(True);  self.piloter("GAUCHE")
        elif touche == Qt.Key.Key_Right:
            self.btn_right.setDown(True); self.piloter("DROITE")
        elif touche == Qt.Key.Key_Space:
            self.btn_monter.setDown(True); self.piloter("MONTER")
        elif touche in (Qt.Key.Key_Control, Qt.Key.Key_Shift):
            self.btn_descendre.setDown(True); self.piloter("DESCENDRE")


    def keyReleaseEvent(self, event):
        if event.isAutoRepeat():
            return
        for btn in [self.btn_up, self.btn_down, self.btn_left, self.btn_right,
                    self.btn_monter, self.btn_descendre]:
            btn.setDown(False)
        self.reinitialiser_statut()


    def piloter(self, direction):
        if self.langue:
            trads = {"AVANCER": "FORWARD", "RECULER": "BACKWARD",
                     "GAUCHE": "LEFT", "DROITE": "RIGHT", "MONTER": "ASCEND",
                     "DESCENDRE": "DESCEND"}
            msg = f"COMMAND: {trads.get(direction, direction)}"
        else:
            msg = f"COMMANDE : {direction}"
        self.label_statut.setText(msg)
        self.label_statut.setStyleSheet(
            "color: #3498db; font-weight: bold; font-family: 'Courier New', monospace; padding: 10px")


    def reinitialiser_statut(self):
        self.label_statut.setText(
            "STATUS : DISCONNECTED" if self.langue else "STATUT : DÉCONNECTÉ")
        self.label_statut.setStyleSheet(
            "color: #e74c3c; font-weight: bold; font-family: 'Courier New', monospace; padding: 10px")


    def appliquer_curseur_perso(self):
        self.curseur_bleu, self.curseur_rouge = style.creer_curseurs()
        self.setCursor(self.curseur_bleu)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    fenetre = StationControleWIL()
    fenetre.show()
    sys.exit(app.exec())
