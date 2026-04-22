import os
import sys

# On ajoute explicitement le chemin des bibliothèques Torch au système
torch_lib_path = os.path.join(os.getenv('LOCALAPPDATA'), 
    r"Packages\PythonSoftwareFoundation.Python.3.11_qbz5n2kfra8p0\LocalCache\local-packages\Python311\site-packages\torch\lib")

if os.path.exists(torch_lib_path):
    os.add_dll_directory(torch_lib_path)
    
import ctypes
import style
from IA.main_IA import fonction_ia
from database_manager import DatabaseManager
from config_manager import charger_configuration, sauvegarder_configuration
from utils import FiltreCurseurLockOn, resource_path
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QProgressBar, QFileDialog, QComboBox, QGridLayout 
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QFont, QIcon
from PyQt6.QtCore import Qt, QRect, QVariantAnimation
from PyQt6.QtWidgets import QListWidget
from random import randint #Pour générer des coordonnées pour les tests

# Ce code permet à Windows d'afficher l'icône personnalisée dans la barre des tâches
try:
    myappid = 'mon_projet.drone_wil.station.v0.1' # Un nom unique
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except Exception:
    pass

class StationControleWIL(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WIL")
        self.setWindowIcon(QIcon(resource_path("assets/logo.ico")))
        self.resize(1000, 600)
        self.setCursor(Qt.CursorShape.CrossCursor)
        
        #Initialisation de la BDD
        self.db = DatabaseManager("projet_wil.db")
        
        # Variables pour l'image et Mael et langue
        self.image_originale = QPixmap()
        self.objets_detectes = []
        self.afficher_boxes = True
        self.langue = charger_configuration() # False : français ; True : anglais
        self.chemin_image_actuelle = ""
        self.message_overlay = "Choisissez une image" # Message par défaut au démarrage
        
        # Lancement de la construction de l'interface
        self.init_ui()
        self.appliquer_style_sombre()
        self.appliquer_textes_langue()
        self.curseur_bleu, self.curseur_rouge = style.creer_curseurs()
        self.filtre_lockon = FiltreCurseurLockOn(self.curseur_rouge)
        
        # --- 1. CRÉATION DES CURSEURS ---
        self.appliquer_curseur_perso()
        self.configurer_interactions_souris()
        
        # --- 2. CRÉATION DU FILTRE "LOCK-ON" ---
        # On lui donne le curseur rouge stocké
        self.filtre_lockon = FiltreCurseurLockOn(self.curseur_rouge, self)
        
        # --- 3. APPLICATION DU FILTRE SUR CHAQUE BOUTON ---
        # Tous les enfants de type QPushButton utiliseront ce filtre
        for bouton in self.findChildren(QPushButton):
            bouton.installEventFilter(self.filtre_lockon)
            
        # --- 4. APPLICATION DU FILTRE SUR LE MENU DEROULANT ---
        self.combo_objets.installEventFilter(self.filtre_lockon)
        self.liste_historique.installEventFilter(self.filtre_lockon)

        # --- APPLIQUER LES TEXTES TRADUITS DÈS LE DÉPART ---
        if self.langue:
            # On appelle une version légère de changer_langue pour forcer les textes anglais
            self.langue = not self.langue # On ruse car changer_langue inverse le booléen
            self.changer_langue()

        #Focus sur le clavier
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        

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

        # --- LOGO ---
        self.label_logo = QLabel()
        pixmap_logo = QPixmap(resource_path("assets/logo_wil_quedar.png")) 
        # On le redimensionne pour qu'il ne prenne pas toute la place 
        self.label_logo.setPixmap(pixmap_logo.scaled(200, 200, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        self.label_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout_telemetrie.addWidget(self.label_logo)
        
        # --- TITRES ---
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

        # --- ALTITUDE ET STATUT ---
        self.label_altitude = QLabel("Altitude : 0.0 m")
        self.label_altitude.setStyleSheet("font-size: 20px; padding: 10px; background: #ecf0f1; border-radius: 5px;")
        layout_telemetrie.addWidget(self.label_altitude)

        self.label_statut = QLabel("STATUT : DÉCONNECTÉ" if not self.langue else "STATUS : DISCONECTED")
        self.label_statut.setStyleSheet("color: red; font-weight: bold; font-family: 'Consolas', 'Courier New', monospace;")
        layout_telemetrie.addWidget(self.label_statut)
        
        self.label_archive = QLabel("")
        self.label_archive.setStyleSheet("color: #2980b9; font-weight: bold;")
        layout_telemetrie.addWidget(self.label_archive)

       # --- SECTION PILOTAGE (D-PAD COMPACT) ---
        self.label_pilotage = QLabel("\n COMMANDES DE VOL")
        self.label_pilotage.setStyleSheet("font-weight: bold; color: #3498db;")
        layout_telemetrie.addWidget(self.label_pilotage)

        layout_fleches = QGridLayout()
        layout_fleches.setSpacing(5) # Un petit espace entre les boutons pour la clarté

        # 1. Création des boutons
        self.btn_up    = QPushButton("▲")
        self.btn_down  = QPushButton("▼")
        self.btn_left  = QPushButton("◀")
        self.btn_right = QPushButton("▶")
        self.btn_monter = QPushButton("▲") 
        self.btn_descendre = QPushButton("▼")

        self.btn_monter.setFixedSize(50, 25)
        self.btn_descendre.setFixedSize(50, 25)

        # 2. Style des boutons 
        style_bouton = "font-size: 18px; font-weight: bold; width: 45px; height: 45px; padding: 0px;"
        for btn in [self.btn_up, self.btn_down, self.btn_left, self.btn_right, self.btn_descendre, self.btn_monter]:
            btn.setStyleSheet(style_bouton)

        # Style spécifique pour les bouton centraux
        style_vertical = "font-size: 16px; font-weight: bold; width: 45px; height: 35px; padding: 0px;"
        self.btn_monter.setStyleSheet(style_vertical + "background-color: #e67e22; border-top-left-radius: 20px; border-top-right-radius: 20px;")
        self.btn_descendre.setStyleSheet(style_vertical + "background-color: #d35400; border-bottom-left-radius: 20px; border-bottom-right-radius: 20px;")

        # 3. Placement dans la Grille (Ligne, Colonne)
        #       Col 0 |   Col 1   | Col 2
        # L0 :        |   AVANT   |       
        # L1 : GAUCHE |  HAUT/BAS | DROITE
        # L2 :        |  ARRIERE  |       
        
        layout_fleches.addWidget(self.btn_up, 0, 1)     # Haut
        layout_fleches.addWidget(self.btn_left, 1, 0)   # Gauche
        layout_fleches.addWidget(self.btn_right, 1, 2)  # Droite
        layout_fleches.addWidget(self.btn_down, 2, 1)   # Bas

        # 3. Placement dans la Grille (On divise la cellule centrale en deux)
        # On utilise un layout vertical très serré pour les coller
        layout_central = QVBoxLayout()
        layout_central.setSpacing(0) # Zéro espace pour l'effet "bloc unique"
        layout_central.setContentsMargins(0, 0, 0, 0)
        layout_central.addWidget(self.btn_monter)
        layout_central.addWidget(self.btn_descendre)

        # On place ce bloc au centre (ligne 1, colonne 1)
        layout_fleches.addLayout(layout_central, 1, 1, Qt.AlignmentFlag.AlignCenter)

        layout_telemetrie.addLayout(layout_fleches)

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
        
        # Style sombre
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
            font-size: 24px; font-weight: bold; color: #ffffff; 
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
        
        # --- DÉSACTIVER LE FOCUS SUR TOUS LES BOUTONS ---
        # Cela permet au clavier de (presque) toujours piloter le drone
        for bouton in self.findChildren(QPushButton):
            bouton.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        # On fait de même pour la liste et le menu déroulant
        self.liste_historique.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.combo_objets.setFocusPolicy(Qt.FocusPolicy.NoFocus)

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

        # --- CONNEXION DES TOUCHES DE PILOTAGE ---
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


    # ==========================================
    # FONCTIONS LOGIQUES
    # ==========================================
    def configurer_interactions_souris(self):
        """
        Applique le curseur par défaut et branche le filtre rouge sur les boutons
        """
        # Curseur bleu pour toute la fenêtre
        self.setCursor(self.curseur_bleu)
        self.combo_objets.setCursor(self.curseur_bleu)
        
        # Liste des boutons qui doivent 'réagir' au survol
        boutons_tactiques = [
            self.btn_monter, self.btn_descendre, 
            self.btn_up, self.btn_down,
            self.btn_right, self.btn_left,
            self.btn_image, self.btn_compter,
            self.btn_langue, self.btn_rapport,
            self.combo_objets 
        ]

        # Force le curseur sur la liste qui descend
        self.combo_objets.view().setCursor(self.curseur_bleu)
        
        # On boucle pour éviter de répéter 'installEventFilter' 8 fois
        for btn in boutons_tactiques:
            btn.installEventFilter(self.filtre_lockon)


    
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

        Entrée :
            -valeur (float) : valeur de l'altitude
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
        # Style de base de la fenêtre
        self.setStyleSheet(style.STYLE_GLOBAL)
        
        # Boutons de menu
        self.btn_image.setStyleSheet(style.STYLE_BOUTON_IMAGE)
        self.btn_langue.setStyleSheet(style.STYLE_BOUTON_LANGUE)
        
        # Commandes de vol (Pilotage)
        self.btn_monter.setStyleSheet(style.STYLE_MONTER)
        self.btn_descendre.setStyleSheet(style.STYLE_DESCENDRE)
        self.btn_up.setStyleSheet(style.STYLE_AVANCER)
        self.btn_down.setStyleSheet(style.STYLE_RECULER)
        self.btn_right.setStyleSheet(style.STYLE_DROITE)
        self.btn_left.setStyleSheet(style.STYLE_GAUCHE)
        
        # Éléments graphiques (Canvas et Néons)
        self.canvas.setStyleSheet("border: 2px solid #89b4fa; background: #000000; border-radius: 10px;")
        style.appliquer_effets_neon(self.label_compteur, self.label_altitude)
        
        # Statut (Déconnecté)
        self.label_statut.setStyleSheet("color: #e74c3c; font-weight: bold; padding: 10px;")



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
            coordonnees = fonction_ia()
            
            # On calcule le nombre d'objets en fonction du nombre de boîtes
            nb_trouve = len(coordonnees) 

            # Mise à jour du compteur avec le nom de l'objet
            texte = f"{type_objet} detected: {nb_trouve}" if self.langue else f"{type_objet} détectés : {nb_trouve}"
            self.label_compteur.setText(texte)
        
            #Affichage de l'altitude
            altitude_actuelle = round(randint(10, 50) + (randint(0, 9) / 10), 1)
            self.animer_altitude(altitude_actuelle) # L'animation remplace le setText direct
            
            self.charger_nouvelle_image(self.chemin_image_actuelle, coordonnees) 
        
            # ENREGISTREMENT avec le type d'objet
            self.enregistrer_capture(self.chemin_image_actuelle, altitude_actuelle, nb_trouve, type_objet)



    def toggle_overlay(self):
        """
        Affichage des rectangles rouges
        """
        self.afficher_boxes = not self.afficher_boxes
        if not self.langue :
            self.btn_toggle.setText("Afficher les détections" if not self.afficher_boxes else "Masquer les détections")
        else:
            self.btn_toggle.setText("Hide detections" if self.afficher_boxes else "Display detections")
        self.dessiner_tout()



    def changer_langue(self):
        """
        Passe la langue de français à anglais et inversement
        """
        self.langue = not self.langue
        
        # On appelle la mise à jour visuelle (ton gros bloc de setText)
        self.appliquer_textes_langue()
        
        # On enregistre via le manager
        sauvegarder_configuration(self.langue)
        

        
    def appliquer_textes_langue(self):
        """
        Change la languedes textes
        """
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
        self.label_pilotage.setText("FLIGHT CONTROLS" if self.langue else "\n COMMANDES DE VOL")
        
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
        sauvegarder_configuration(self.langue)
        


    def charger_nouvelle_image(self, chemin, coordonnees):
        """
        Permet de charger une image et ses métadonnées

        Entrée : 
            - chemin (str) :chemin de l'image
            - coordonnes (list ou Qrect) : liste des coordonnées des objets détectés    
        """
        # 1. Chargement et vérification de l'image
        self.image_originale = QPixmap(chemin)
        
        if self.image_originale.isNull():
            self.message_overlay = "ERROR" if self.langue else "ERREUR : Fichier introuvable !"
            self.dessiner_tout()
            return

        # 2. Nettoyage du message d'erreur si l'image est valide
        self.message_overlay = ""

        # 3. Conversion intelligente des coordonnées 
        # On vérifie : 1. Si la liste n'est pas vide / 2. Si le premier élément n'est pas déjà un QRect
        if coordonnees and not isinstance(coordonnees[0], QRect):
            self.objets_detectes = [QRect(x, y, w, h) for (x, y, w, h) in coordonnees]
        else:
            # Si c'est déjà des QRect ou une liste vide, on assigne directement
            self.objets_detectes = coordonnees if coordonnees else []

        # 4. Mise à jour de l'UI 
        nb = len(self.objets_detectes)
        self.label_compteur.setText(f"Detected objects: {nb}" if self.langue else f"Objets détectés : {nb}")
        
        # 5. Rafraîchissement global
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
            pixmap_logo = QPixmap(resource_path("assets/logo_wil_quedar_radar.png"))
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
        h = self.db.sauvegarder_mission(chemin, altitude, nb, type_objet, self.objets_detectes)
        
        # L'UI s'occupe de l'affichage uniquement
        self.liste_historique.addItem(f"[{h}] - {nb} {type_objet} (Alt: {altitude}m)")



    def generer_rapport(self):
        """
        Exporte les données de la base en fichier CSV avec les coordonnées
        """
        try:
            # On demande au manager de faire le fichier
            chemin = self.db.exporter_csv(self.langue)
            
            # Mise à jour de l'UI
            texte = f"Rapport généré dans {chemin}" if not self.langue else f"Report generated in {chemin}"
            self.label_archive.setText(texte)
            self.label_archive.setStyleSheet("color: #2ecc71; font-weight: bold;")
        except Exception as e:
            self.label_archive.setText("Erreur export CSV")
            print(e)



    def charger_depuis_historique(self, item):
        """
        Pemret de charger une image depuis l'historique des analyses

        Entrée :
            - item (QListWidgetItem) : ligne de l'historique sur
        """
        texte_complet = item.text() 
        try:
            # 1. Extraction de l'horodatage du texte de la liste
            # Format attendu : "[HH:MM:SS] - ..."
            horodatage = texte_complet.split(']')[0].replace('[', '')
            
            # 2. APPEL AU MANAGER (Remplace self.conn.cursor)
            resultat = self.db.recuperer_mission_par_horodatage(horodatage)
            
            if resultat:
                chemin, nb, type_obj, chaine_coords, altitude = resultat
                
                # 3. CONVERSION DES COORDONNÉES (texte -> QRect)
                nouvelles_coords = []
                if chaine_coords:
                    for bloc in chaine_coords.split(';'):
                        if bloc: # Sécurité si la chaîne finit par ;
                            x, y, w, h = map(int, bloc.split(','))
                            nouvelles_coords.append(QRect(x, y, w, h))
                
                # 4. MISE À JOUR DE L'INTERFACE
                self.chemin_image_actuelle = chemin
                
                # On met à jour l'image et les boîtes
                self.charger_nouvelle_image(chemin, nouvelles_coords) 
                
                # Animation de l'altitude
                self.animer_altitude(altitude)
                
                # Mise à jour du label archive
                msg = f"Archive : {horodatage} ({nb} {type_obj})" if not self.langue else f"Archive: {horodatage} ({nb} {type_obj})"
                self.label_archive.setText(msg)
                self.label_archive.setStyleSheet("color: #2980b9; font-weight: bold;")
            
        except Exception as e:
            print(f"Erreur historique (UI) : {e}")



    def keyPressEvent(self, event):
        """
        Gestion du clavier - Appui

        Entrée :
            - event : touche préssée
        """
        if event.isAutoRepeat(): return # Évite les bugs de répétition
        
        touche = event.key()
        if touche == Qt.Key.Key_Up:
            self.btn_up.setDown(True)
            self.piloter("AVANCER")
        elif touche == Qt.Key.Key_Down:
            self.btn_down.setDown(True)
            self.piloter("RECULER")
        elif touche == Qt.Key.Key_Left:
            self.btn_left.setDown(True)
            self.piloter("GAUCHE")
        elif touche == Qt.Key.Key_Right:
            self.btn_right.setDown(True)
            self.piloter("DROITE")
        elif touche == Qt.Key.Key_Space:
            self.btn_monter.setDown(True)
            self.piloter("MONTER")
        elif touche == Qt.Key.Key_Control or touche == Qt.Key.Key_Shift:
            self.btn_descendre.setDown(True)
            self.piloter("DESCENDRE")



    def keyReleaseEvent(self, event):
        """
        Gestion du clavier - Relâchement

        Entrée :
            - event : touche préssée
        """
        if event.isAutoRepeat(): return
        
        # On réinitialise tous les boutons (incluant les deux nouveaux)
        for btn in [self.btn_up, self.btn_down, self.btn_left, self.btn_right, self.btn_monter, self.btn_descendre]:
            btn.setDown(False)
            
        self.reinitialiser_statut()



    def piloter(self, direction):
        """
        Affiche la commande active en bleu
        """
        msg = f"COMMANDE : {direction}"
        if self.langue:
            trads = {"AVANCER":"FORWARD", "RECULER":"BACKWARD", "GAUCHE":"LEFT", "DROITE":"RIGHT", "MONTER":"ASCEND"}
            msg = f"COMMAND: {trads.get(direction, direction)}"
        
        self.label_statut.setText(msg)
        self.label_statut.setStyleSheet("color: #3498db; font-weight: bold; font-family: 'Courier New', monospace; padding: 10px")



    def reinitialiser_statut(self):
        """
        Revient au message par défaut en rouge
        """
        self.label_statut.setText("STATUS : DISCONNECTED" if self.langue else "STATUT : DÉCONNECTÉ")
        self.label_statut.setStyleSheet("color: #e74c3c; font-weight: bold; font-family: 'Courier New', monospace; padding: 10px")



    def appliquer_curseur_perso(self):
        """
        Crée et applique le viseur de base (bleu) et prépare la version rouge
        """
        # On récupère les deux curseurs depuis le fichier styles
        self.curseur_bleu, self.curseur_rouge = style.creer_curseurs()
        self.setCursor(self.curseur_bleu)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    fenetre = StationControleWIL()
    fenetre.show()
    sys.exit(app.exec())