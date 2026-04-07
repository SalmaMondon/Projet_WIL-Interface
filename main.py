import sys
import sqlite3
import csv
import os
import json
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QProgressBar, QFileDialog, QGraphicsDropShadowEffect, QComboBox
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QFont
from PyQt6.QtCore import Qt, QRect, QVariantAnimation
from PyQt6.QtWidgets import QListWidget
from datetime import datetime
from random import randint #Pour générer des coordonnées pour les tests

class StationControleWIL(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WIL")
        self.resize(1000, 600)
        
        #Initialisation de la BDD
        self.init_base_de_donnees()
        
        # Variables pour l'image et Mael
        self.image_originale = QPixmap()
        self.objets_detectes = []
        self.afficher_boxes = True
        self.langue = self.charger_config() # False : français ; True : anglais
        self.chemin_image_actuelle = ""
        self.message_overlay = "Choisissez une image" # Message par défaut au démarrage
        
        # Lancement de la construction de l'interface
        self.init_ui()
        self.appliquer_style_sombre()

        # --- APPLIQUER LES TEXTES TRADUITS DÈS LE DÉPART ---
        if self.langue:
            # On appelle une version légère de changer_langue pour forcer les textes anglais
            self.langue = not self.langue # On ruse car changer_langue inverse le booléen
            self.changer_langue()



    def charger_config(self):
        """Charge la langue depuis le fichier JSON, ou français par défaut"""
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r") as f:
                    config = json.load(f)
                    # On transforme la chaîne "en"/"fr" en booléen pour self.langue
                    return config.get("langue") == "en"
            except:
                return False # Français par défaut en cas d'erreur
        return False

    def sauvegarder_config(self):
        """Enregistre le choix de langue actuel dans le fichier JSON"""
        config = {"langue": "en" if self.langue else "fr"}
        with open("config.json", "w") as f:
            json.dump(config, f)
        
    def init_base_de_donnees(self):
        """
        Création de la base de donnée ou utilisation de l'ancienne si elle existe déjà
        """
        self.conn = sqlite3.connect("projet_wil.db")
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS missions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                horodatage TEXT,
                chemin_image TEXT,
                altitude REAL,
                nb_objets INTEGER,
                coordonnees TEXT,
                type_objet TEXT  
            )
        ''')
        self.conn.commit()



    def init_ui(self):
        """
        Création de l'interface graphique
        """
        # Layout Global : Gauche (Télémétrie) | Droite (Image et historique)
        layout_global = QHBoxLayout()
        
        # ==========================================
        # 1. SECTION TÉLÉMÉTRIE (GAUCHE)
        # ==========================================
        layout_telemetrie = QVBoxLayout()

        self.label_logo = QLabel()
        pixmap_logo = QPixmap("assets/logo_wil_quedar.png") 
        # On le redimensionne pour qu'il ne prenne pas toute la place (ex: 200px de large)
        self.label_logo.setPixmap(pixmap_logo.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.label_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_telemetrie.addWidget(self.label_logo)
        
        self.label_titre = QLabel("\n DONNÉES DE BORD")
        self.label_titre.setStyleSheet("font-weight: bold; font-size: 16px; color: #3498db;")
        layout_telemetrie.addWidget(self.label_titre)

        self.label_batterie = QLabel("Batterie :")
        layout_telemetrie.addWidget(self.label_batterie)
        # --- WIDGET BATTERIE STYLE ---
        layout_batterie_container = QHBoxLayout() # Pour centrer la batterie
        
        self.barre_batterie = QProgressBar()
        self.barre_batterie.setValue(100)
        self.barre_batterie.setFixedSize(150, 40) # Taille fixe pour garder la forme
        self.barre_batterie.setTextVisible(False) # On cache le texte interne pour le style
        
        # Le style QSS magique
        self.barre_batterie.setStyleSheet("""
            QProgressBar {
                border: 3px solid #7f8c8d;
                border-radius: 5px;
                background-color: #2c3e50;
                margin-right: 10px; /* Espace pour le petit embout */
            }
            QProgressBar::chunk {
                background-color: #2ecc71;
                width: 10px; /* Donne un effet de cellules séparées */
                margin: 2px;
            }
        """)
        
        # Création du petit embout (le "+" de la pile)
        self.embout_batterie = QLabel()
        self.embout_batterie.setFixedSize(8, 20)
        self.embout_batterie.setStyleSheet("background-color: #7f8c8d; border-radius: 2px;")

        #Crétaion du pourcentage de batterie
        self.pourcentage_batterie = QLabel(f"{self.barre_batterie.value()}%") 
        self.pourcentage_batterie.setStyleSheet("color: white; font-weight: bold; margin-left: 5px;")
        
        layout_batterie_container.addWidget(self.barre_batterie)
        layout_batterie_container.addWidget(self.embout_batterie)
        layout_batterie_container.addWidget(self.pourcentage_batterie)
        layout_batterie_container.addStretch() # Aligner à gauche
        
        layout_telemetrie.addLayout(layout_batterie_container)

        self.label_altitude = QLabel("Altitude : 0.0 m")
        self.label_altitude.setStyleSheet("font-size: 20px; padding: 10px; background: #ecf0f1; border-radius: 5px;")
        layout_telemetrie.addWidget(self.label_altitude)

        self.label_statut = QLabel("STATUT : DÉCONNECTÉ" if not self.langue else "STATUS : DISCONECTED")
        self.label_statut.setStyleSheet("color: red; font-weight: bold; font-family: 'Consolas', 'Courier New', monospace;")
        layout_telemetrie.addWidget(self.label_statut)
        
        self.label_archive = QLabel("")
        self.label_archive.setStyleSheet("color: #2980b9; font-weight: bold;")
        layout_telemetrie.addWidget(self.label_archive)

        layout_telemetrie.addStretch()
        layout_global.addLayout(layout_telemetrie, stretch=1)
        
        self.layout_historique = QVBoxLayout()
        self.label_historique = QLabel("Historique" if not self.langue else "History")
        self.layout_historique.addWidget(self.label_historique)

        self.liste_historique = QListWidget()
        self.liste_historique.itemClicked.connect(self.charger_depuis_historique)
        self.layout_historique.addWidget(self.liste_historique)

        self.btn_rapport = QPushButton("Générer un rapport CSV")
        self.btn_rapport.clicked.connect(self.generer_rapport)
        self.layout_historique.addWidget(self.btn_rapport)

        # --- MENU DÉROULANT DE SÉLECTION D'OBJET ---
        self.layout_type_objet = QLabel("Type d'objet à détecter :")
        layout_telemetrie.addWidget(self.layout_type_objet)
        self.combo_objets = QComboBox()
        self.combo_objets.addItems(["Moutons", "Voitures", "Humains", "Bâtiments"])
        
        # Style pour correspondre à mon design sombre
        self.combo_objets.setStyleSheet("""
            QComboBox {
                background-color: #34495e;
                color: white;
                border-radius: 5px;
                padding: 5px;
                font-weight: bold;
            }
            QComboBox QAbstractItemView {
                background-color: #1e1e2e;
                color: white;
                selection-background-color: #3498db;
            }
        """)
        layout_telemetrie.addWidget(self.combo_objets)

        # ==========================================
        # 2. SECTION IMAGE ET ANALYSE (DROITE)
        # ==========================================
        layout_droite = QVBoxLayout()
        
        # Compteur
        self.label_compteur = QLabel("Objets détectés : 0")
        self.label_compteur.setStyleSheet("""
            font-size: 24px; font-weight: bold; color: #27ae60; 
            background: rgba(255, 255, 255, 150); border-radius: 10px;
        """)
        self.label_compteur.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout_droite.addWidget(self.label_compteur)

        # Zone d'affichage image (Canvas) 
        self.canvas = QLabel("Aucune image")
        self.canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canvas.setMinimumSize(640, 480)
        self.canvas.setStyleSheet("border: 2px solid #2c3e50; background: black; color: white;")
        layout_droite.addWidget(self.canvas, stretch=4)
        
        # ==========================================
        # 3. SECTION COMMANDES (BAS DROITE)
        # ==========================================
        layout_commandes = QHBoxLayout()
        
        self.btn_image = QPushButton("Choisir une image")
        self.btn_image.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold;")
        
        self.btn_compter = QPushButton("Compter les objets")
        self.btn_toggle = QPushButton("Masquer les détections")

        self.btn_langue = QPushButton("Switch to English")
        self.btn_langue.setStyleSheet("background-color: #960018; color: white; font-weight: bold; ")

        layout_commandes.addWidget(self.btn_image)
        layout_commandes.addWidget(self.btn_compter)
        layout_commandes.addWidget(self.btn_toggle)
        layout_commandes.addWidget(self.btn_langue)
        
        layout_droite.addLayout(layout_commandes)
        
        # Ajout de la partie droite au layout global
        layout_global.addLayout(layout_droite, stretch=4)
        layout_global.addLayout(self.layout_historique, stretch=1)
        
        # Application de l'unique layout global à la fenêtre
        self.setLayout(layout_global)
        self.dessiner_tout() # Force l'affichage du radar au démarrage

        # ==========================================
        # 4. CONNEXION DES BOUTONS (SLOTS)
        # ==========================================
        self.btn_image.clicked.connect(self.action_image)
        self.btn_compter.clicked.connect(self.action_compter)
        self.btn_toggle.clicked.connect(self.toggle_overlay)
        self.btn_langue.clicked.connect(self.changer_langue) 



    # ==========================================
    # 5. FONCTIONS LOGIQUES
    # ==========================================
    def animer_altitude(self, nouvelle_valeur):
        """
        Permet de faire défiler l'altitude sur l'interface

        Entrée : 
            -nouvelle_valeur (float) : nouvelle altitude à afficher 
        """
        # 1. On récupère la valeur actuelle affichée (on enlève "Altitude : " et " m")
        try:
            valeur_actuelle = float(self.label_altitude.text().split(":")[1].replace("m", "").strip())
        except:
            valeur_actuelle = 0.0

        # 2. Configuration de l'animation
        self.animation = QVariantAnimation(self)
        self.animation.setStartValue(valeur_actuelle)
        self.animation.setEndValue(float(nouvelle_valeur))
        self.animation.setDuration(1000) # Durée : 1 seconde
        
        # 3. À chaque étape de l'animation, on met à jour le texte
        self.animation.valueChanged.connect(self.mettre_a_jour_label_altitude)
        self.animation.start()



    def mettre_a_jour_label_altitude(self, valeur):
        """
        Affichage de la valeur de l'altitude
        """
        self.label_altitude.setText(f"Altitude : {valeur:.1f} m")



    def mettre_a_jour_batterie(self, valeur):
        """
        Affichage de la batterie, changement de couleur si batterie faible
        
        Entrée :
            -valeur (int) : pourcentage de batterie restant
        """
        # 1. Mise à jour de la barre
        self.barre_batterie.setValue(valeur)
    
        # 2. Mise à jour du texte (Correction ici)
        self.pourcentage_batterie.setText(f"{valeur}%")
        
        # 3. Changement de couleur dynamique (Optionnel mais stylé)
        if valeur > 50:
            couleur = "#2ecc71" # Vert
        elif valeur > 20:
            couleur = "#f39c12" # Orange
        else:
            couleur = "#e74c3c" # Rouge
            
        self.barre_batterie.setStyleSheet(f"""
            QProgressBar {{
                border: 3px solid #7f8c8d;
                border-radius: 5px;
                background-color: #2c3e50;
                margin-right: 10px;
            }}
            QProgressBar::chunk {{
                background-color: {couleur};
                width: 10px;
                margin: 2px;
            }}
        """)



    def appliquer_style_sombre(self):
        """
        Définis le style sombre globale de l'interface
        """
        # 1. STYLE GLOBAL SOMBRE
        self.setStyleSheet("""
            QWidget { background-color: #1e1e2e; color: #cdd6f4; font-family: 'Consolas', 'Courier New', monospace; }
            QPushButton {background-color: #34495e; color: white; font-weight: bold; border-radius: 8px; padding: 10px;}
            QPushButton:hover { background-color: #2c3e50; }
            QListWidget { background-color: #181825; color: #a6adc8; }
        """)

        self.canvas.setStyleSheet("border: 2px solid #89b4fa; background: #000000; border-radius: 10px;")

        self.btn_image.setStyleSheet("""
            QPushButton { background-color: #2ecc71; color: white; font-family: 'Consolas', 'Courier New', monospace; font-weight: bold; border-radius: 8px; padding: 10px;}
            QPushButton:hover { background-color: #28b062; }
        """)

        self.btn_langue.setStyleSheet("""
            QPushButton { background-color: #960018; color: white; font-family: 'Consolas', 'Courier New', monospace; font-weight: bold; border-radius: 8px; padding: 10px;}
            QPushButton:hover { background-color: #850007; }
        """)

        self.label_statut.setStyleSheet("color: #e74c3c; font-weight: bold; font-family: 'Courier New', monospace; border-radius: 8px; padding: 10px")
        
        # 2. NÉON VERT POUR LE COMPTEUR
        neon_vert = QGraphicsDropShadowEffect()
        neon_vert.setColor(QColor(166, 227, 161, 255)) 
        neon_vert.setBlurRadius(25)
        neon_vert.setOffset(0, 0)
        self.label_compteur.setGraphicsEffect(neon_vert)
        self.label_compteur.setStyleSheet("font-size: 24px; font-weight: bold; color: #f1ffed; background: transparent;")

        # 3. NÉON BLEU POUR L'ALTITUDE 
        neon_bleu = QGraphicsDropShadowEffect()
        neon_bleu.setColor(QColor(137, 180, 250, 200)) # Bleu clair
        neon_bleu.setBlurRadius(20)
        neon_bleu.setOffset(0, 0)
        self.label_altitude.setGraphicsEffect(neon_bleu)
        self.label_altitude.setStyleSheet("font-size: 20px; padding: 10px; color: #b4befe; background: transparent;")



    def action_image(self):
        """
        Permet de choisir l'image à analyser
        """
        # 1. Ouvre une fenêtre pour choisir le fichier manuellement
        chemin_fichier, _ = QFileDialog.getOpenFileName(
            self, 
            "Sélectionner la photo du dirigeable", 
            "C:/Users/Lenovo/Pictures", # Le dossier qui s'ouvre par défaut
            "Images (*.png *.jpeg *.jpg *.bmp);;Tous les fichiers (*)"
        )
        
        # 2. Si une image est séléctionnée (pas d'annulation)
        if chemin_fichier:
            self.message_overlay = "" # On efface le message puisque l'image arrive
            self.chemin_image_actuelle = chemin_fichier
            self.charger_nouvelle_image(chemin_fichier, [])



    def action_compter(self):
        """
        Permet de compter les objets en se basant sur l'analyse d'image.
        Actuellement, comportement aléatoire
        """
        if self.image_originale.isNull() or not self.chemin_image_actuelle :
            # On change la variable et on redessine
            self.message_overlay = ("ERREUR : Chargez une image d'abord !" if not self.langue else "ERROR : load a picture first !")
            self.dessiner_tout()
            return
        
        # On récupère le type d'objet sélectionné dans le menu
        type_objet = self.combo_objets.currentText()
    
        if not self.image_originale.isNull():
            # Simulation des données de Mael et Anaïs
            # On crée une liste de 5 rectangles différents [x, y, largeur, hauteur]
            fausses_coordonnees = [tuple(randint(50, 400) for _ in range(4)) for _ in range(randint(2, 10))]
            
            # On calcule le nombre d'objets en fonction du nombre de boîtes
            nb_trouve = len(fausses_coordonnees) 

            # Mise à jour du compteur avec le nom de l'objet
            texte = f"{type_objet} detected: {nb_trouve}" if self.langue else f"{type_objet} détectés : {nb_trouve}"
            self.label_compteur.setText(texte)
        
            #Affichage de l'altitude
            altitude_actuelle = round(randint(10, 50) + (randint(0, 9) / 10), 1)
            self.animer_altitude(altitude_actuelle) # L'animation remplace le setText direct
            
            self.charger_nouvelle_image(self.chemin_image_actuelle, fausses_coordonnees) 
        
            # ENREGISTREMENT avec le type d'objet
            self.enregistrer_capture(self.chemin_image_actuelle, altitude_actuelle, nb_trouve, type_objet)



    def toggle_overlay(self):
        """
        Affichage des rectangles rouges
        """
        self.afficher_boxes = not self.afficher_boxes
        self.btn_toggle.setText("Afficher les détections" if not self.afficher_boxes else "Masquer les détections")
        self.dessiner_tout()



    def changer_langue(self):
        """
        Bascule l'intégralité de l'interface entre le français et l'anglais
        """
        self.langue = not self.langue
        
        # 1. Textes des boutons
        self.btn_langue.setText("Switch to English" if not self.langue else "Passer en français")
        self.btn_compter.setText("Count objects" if self.langue else "Compter les objets")
        self.btn_image.setText("Choose a picture" if self.langue else "Choisir une image")
        self.btn_rapport.setText("Generate CSV report" if self.langue else "Générer un rapport CSV")
        
        # 2. Labels de structure
        self.label_titre.setText("\n ONBOARD DATA" if self.langue else "\n DONNÉES DE BORD")
        self.layout_type_objet.setText("Object type:" if self.langue else "Type d'objet à détecter :")
        self.label_statut.setText("STATUT : DÉCONNECTÉ" if not self.langue else "STATUS : DISCONECTED")
        self.label_historique.setText("Historique" if not self.langue else "History")
        self.label_batterie.setText("Batterie" if not self.langue else "Battery")
        
        # 3. Mise à jour du menu déroulant (Combo Box)
        current_idx = self.combo_objets.currentIndex()
        self.combo_objets.clear()
        if self.langue:
            self.combo_objets.addItems(["Sheep", "Cars", "Humans", "Buildings"])
        else:
            self.combo_objets.addItems(["Moutons", "Voitures", "Humains", "Bâtiments"])
        self.combo_objets.setCurrentIndex(current_idx)

        # 4. Message du Radar (Overlay)
        if self.message_overlay != "":
            if "Choisissez" in self.message_overlay or "Choose" in self.message_overlay:
                self.message_overlay = "Choose a picture" if self.langue else "Choisissez une image"
            elif "ERREUR" in self.message_overlay or "ERROR" in self.message_overlay:
                self.message_overlay = "ERROR: Load an image first!" if self.langue else "ERREUR : Chargez une image d'abord !"

        # 5. Rafraîchir les labels dynamiques (Altitude et Compteur)
        # On récupère la valeur actuelle pour changer juste le préfixe
        try:
            alt_val = float(self.label_altitude.text().split(":")[1].replace("m", "").strip())
            
            # Pour le compteur, on extrait juste le chiffre à la fin
            nb_val = self.label_compteur.text().split(":")[-1].strip()
            type_obj = self.combo_objets.currentText()
            self.label_compteur.setText(f"Detected objetcs: {nb_val}" if self.langue else f"Objets détectés : {nb_val}")
        except:
            pass

        # 6. Bouton Toggle (Masquer/Afficher)
        if self.langue:
            self.btn_toggle.setText("Hide detections" if self.afficher_boxes else "Display detections")
        else:
            self.btn_toggle.setText("Masquer les détections" if self.afficher_boxes else "Afficher les détections")

        # 7. Forcer le redessin du Radar ou de l'image
        self.dessiner_tout()

        # 8. Enregistrer le changement de langue
        self.sauvegarder_config()



    def charger_nouvelle_image(self, chemin, coordonnees):
        """
        Permet de charger une image et ses métadonnées

        Entrée : 
            - chemin (str) :chemin de l'image
            - coordonnes (list ou Qrect) : liste des coordonnées des objets détectés    
        """
        self.image_originale = QPixmap(chemin)
        
        if self.image_originale.isNull():
            # Au lieu de self.canvas.setText, on utilise l'overlay
            self.message_overlay = "ERREUR : Fichier introuvable !"
            # On force le radar à se redessiner avec ce nouveau message
            self.dessiner_tout()
            return

        # Si l'image est trouvée, on vide le message pour ne pas polluer l'affichage futur
        self.message_overlay = ""

        # Code pour convertir les coordonnées
        if coordonnees and not isinstance(coordonnees[0], QRect):
            self.objets_detectes_detectes = [QRect(x, y, w, h) for (x, y, w, h) in coordonnees]
        else:
            self.objets_detectes_detectes = coordonnees

        self.label_compteur.setText(f"Objets détectés : {len(self.objets_detectes)}")
        self.dessiner_tout()

        # Si on reçoit des données et que ce ne sont pas déjà des QRect, on les convertit
        if coordonnees and not isinstance(coordonnees[0], QRect):
            self.objets_detectes = [QRect(x, y, w, h) for (x, y, w, h) in coordonnees]
        else:
            # Sinon (si c'est déjà des QRect ou une liste vide), on prend tel quel
            self.objets_detectes = coordonnees

        self.label_compteur.setText(f"Objets détectés : {len(self.objets_detectes)}")
        self.dessiner_tout()



    def dessiner_tout(self):
        """
        Permet d'actualiser l'affichage dans le canvas
        """
        # --- CAS 1 : MODE VEILLE (RADAR) ---
        if self.image_originale.isNull():
            self.canvas.setScaledContents(True)
            largeur = max(self.canvas.width(), 640)
            hauteur = max(self.canvas.height(), 480)
            
            fond_veille = QPixmap(largeur, hauteur)
            fond_veille.fill(QColor("#0b0e14"))
            
            painter = QPainter(fond_veille)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # --- 1. DESSIN DE LA GRILLE ---
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

            # --- 2. DESSIN DU LOGO (FILIGRANE) ---
            # Attention au nom du fichier ici ! 
            pixmap_logo = QPixmap("assets/logo_wil_quedar_radar.png") 
            if not pixmap_logo.isNull():
                painter.setOpacity(0.2)
                logo_redim = pixmap_logo.scaled(300, 300, Qt.AspectRatioMode.KeepAspectRatio)
                x_logo = (largeur - logo_redim.width()) // 2
                y_logo = (hauteur - logo_redim.height()) // 2
                painter.drawPixmap(x_logo, y_logo, logo_redim)
            
            # --- 3. DESSIN DU TEXTE (OVERLAY) ---
            if self.message_overlay:
                painter.setOpacity(1.0) # On remet l'opacité à 100%
                
                # Configuration de la police
                police_radar = QFont("Consolas", 18)
                police_radar.setBold(True)
                police_radar.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 110)
                painter.setFont(police_radar)
                
                # Couleur
                couleur = QColor("#ff5555") if "ERREUR" in self.message_overlay else QColor("#89b4fa")
                painter.setPen(couleur)
                
                # Positionnement (centré)
                rect_texte = fond_veille.rect().adjusted(20, 20, -20, -20)
                painter.drawText(
                    rect_texte, 
                    Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, 
                    self.message_overlay
                )

            painter.end() # ON APPELLE END() UNE SEULE FOIS À LA FIN
            self.canvas.setPixmap(fond_veille)
            return

        # --- CAS 2 : IMAGE PRÉSENTE ---
        self.canvas.setScaledContents(False)
        image_a_afficher = self.image_originale.copy()
        
        if self.afficher_boxes and self.objets_detectes:
            painter = QPainter(image_a_afficher)
            painter.setPen(QPen(QColor(255, 50, 50), 3))
            
            for rect in self.objets_detectes:
                x, y, w, h = rect.getRect()
                t = int(min(w, h) * 0.25)
                
                # 1. DESSIN DES COINS 
                painter.drawLine(x, y, x + t, y); painter.drawLine(x, y, x, y + t)
                painter.drawLine(x + w, y, x + w - t, y); painter.drawLine(x + w, y, x + w, y + t)
                painter.drawLine(x, y + h, x + t, y + h); painter.drawLine(x, y + h, x, y + h - t)
                painter.drawLine(x + w, y + h, x + w - t, y + h); painter.drawLine(x + w, y + h, x + w, y + h - t)

                # 2. AJOUT DU POINT CENTRAL
                # On définit un pinceau plein pour le point
                painter.setBrush(QColor(255, 50, 50)) 
                
                # Calcul du centre du rectangle
                centre_x = x + (w // 2)
                centre_y = y + (h // 2)
                
                # On dessine un petit cercle de 6 pixels de rayon
                rayon = 6
                painter.drawEllipse(centre_x - (rayon//2), centre_y - (rayon//2), rayon, rayon)
                
                # On réinitialise le pinceau à "vide" pour ne pas remplir les prochains coins
                painter.setBrush(Qt.BrushStyle.NoBrush)

            painter.end()

        #Redimensionnement
        pixmap_redim = image_a_afficher.scaled(
            self.canvas.width(), self.canvas.height(), 
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.canvas.setPixmap(pixmap_redim)
    


    def enregistrer_capture(self, chemin, altitude, nb, type_objet): 
        """
        Enregistre les image et leur données dans la BDD

        Entrée :
            - chemin (str) : chemin pour accéder à l'image
            - altitude (float) : altitude du drône
            - nb (int) : nombre d'objets comptés
            - type_objet (str) : type d'objets comptés (moutons, voitures...)
        """
        horodatage = datetime.now().strftime("%H:%M:%S")
        
        liste_coords = [f"{r.x()},{r.y()},{r.width()},{r.height()}" for r in self.objets_detectes]
        chaine_coords = ";".join(liste_coords)

        cursor = self.conn.cursor()
        # Requête SQl
        cursor.execute("""
            INSERT INTO missions (horodatage, chemin_image, altitude, nb_objets, coordonnees, type_objet) 
            VALUES (?, ?, ?, ?, ?, ?)""",
            (horodatage, chemin, altitude, nb, chaine_coords, type_objet))
        self.conn.commit()
        
        self.liste_historique.addItem(f"[{horodatage}] - {nb} {type_objet} (Alt: {altitude}m)")



    def generer_rapport(self):
        """
        Exporte les données de la base en fichier CSV avec les coordonnées
        """
        try:
            # 1. Préparer le dossier de destination
            dossier_sortie = "rapports"
            if not os.path.exists(dossier_sortie):
                os.makedirs(dossier_sortie) # Crée le dossier s'il n'existe pas


            cursor = self.conn.cursor()
            cursor.execute("SELECT id, horodatage, chemin_image, altitude, nb_objets, type_objet, coordonnees FROM missions")
            data = cursor.fetchall()
            
            # 2. Construire le nom et le CHEMIN COMPLET
            nom_fichier = f"rapport_mission_{datetime.now().strftime('%d_%m_%Y')}.csv"
            chemin_complet = os.path.join(dossier_sortie, nom_fichier) # Résultat : "rapports/rapport_mission_..."
            
            # 3. Ouvrir le fichier avec le chemin complet
            with open(chemin_complet, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter=';')
                writer.writerow(["ID", "Heure", "Chemin Image", "Altitude (m)", "Nombre", "Type", "Coordonnées"])
                writer.writerows(data)

            # Mise à jour de l'UI
            self.label_archive.setText(f"Rapport généré dans /rapports" if not self.langue else "Report generated in /rapports")
            self.label_archive.setStyleSheet("color: #2ecc71; font-weight: bold;")

        except Exception as e:
            print(f"Erreur lors de la génération du rapport : {e}")
            self.label_archive.setText("Erreur lors de l'export CSV")



    def charger_depuis_historique(self, item):
        """
        Pemret de charger une image depuis l'historique des analyses

        Entrée :
            - item (QListWidgetItem) : ligne de l'historique sur
        """
        texte_complet = item.text() 
        try:
            # 1. On extrait l'horodatage pour retrouver la ligne en BDD
            horodatage = texte_complet.split(']')[0].replace('[', '')
            
            cursor = self.conn.cursor()
            # --- MODIFICATION : On ajoute 'altitude' à la requête SELECT ---
            cursor.execute("SELECT chemin_image, nb_objets, type_objet, coordonnees, altitude FROM missions WHERE horodatage = ?", (horodatage,))
            resultat = cursor.fetchone()
            
            if resultat:
                # On récupère les 5 valeurs demandées dans le SELECT
                chemin, nb, type_obj, chaine_coords, altitude = resultat
                
                # 3. Conversion des coordonnées (texte -> QRect)
                nouvelles_coords = []
                if chaine_coords:
                    for bloc in chaine_coords.split(';'):
                        x, y, w, h = map(int, bloc.split(','))
                        nouvelles_coords.append(QRect(x, y, w, h))
                
                # 4. MISE À JOUR DE L'INTERFACE
                self.chemin_image_actuelle = chemin
                
                # On met à jour l'image et les boîtes
                self.charger_nouvelle_image(chemin, nouvelles_coords) 
                
                # ON AJOUTE LA MISE À JOUR DE L'ALTITUDE (avec animation)
                self.animer_altitude(altitude)
                
                # Mise à jour du label archive avec le bon type
                self.label_archive.setText(f"Archive : {horodatage} ({nb} {type_obj})")
                self.label_archive.setStyleSheet("color: #2980b9; font-weight: bold;")
            
        except Exception as e:
            print(f"Erreur historique : {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    fenetre = StationControleWIL()
    fenetre.show()
    sys.exit(app.exec())