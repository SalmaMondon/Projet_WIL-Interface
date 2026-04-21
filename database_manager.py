import sqlite3
import os
import csv
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_name="projet_wil.db"):
        self.db_name = db_name
        self.conn = sqlite3.connect(self.db_name)
        self.init_db()

    def init_db(self):
        """Crée la table si elle n'existe pas."""
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

    def sauvegarder_mission(self, chemin, altitude, nb, type_objet, objets_detectes):
        """Enregistre une capture et retourne l'horodatage pour l'UI."""
        horodatage = datetime.now().strftime("%H:%M:%S")
        
        # Transformation des QRect en chaîne de caractères
        liste_coords = [f"{r.x()},{r.y()},{r.width()},{r.height()}" for r in objets_detectes]
        chaine_coords = ";".join(liste_coords)

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO missions (horodatage, chemin_image, altitude, nb_objets, coordonnees, type_objet) 
            VALUES (?, ?, ?, ?, ?, ?)""",
            (horodatage, chemin, altitude, nb, chaine_coords, type_objet))
        self.conn.commit()
        
        return horodatage # On renvoie l'heure pour que l'UI puisse l'afficher

    def exporter_csv(self, est_anglais):
        """Génère le rapport CSV. Retourne le chemin du fichier ou lève une exception."""
        dossier_sortie = "rapports"
        if not os.path.exists(dossier_sortie):
            os.makedirs(dossier_sortie)

        cursor = self.conn.cursor()
        cursor.execute("SELECT id, horodatage, chemin_image, altitude, nb_objets, type_objet, coordonnees FROM missions")
        data = cursor.fetchall()
        
        nom_fichier = f"rapport_mission_{datetime.now().strftime('%d_%m_%Y')}.csv"
        chemin_complet = os.path.join(dossier_sortie, nom_fichier)
        
        with open(chemin_complet, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=';')
            if est_anglais:
                writer.writerow(["ID", "Hour", "Image Path", "Altitude (m)", "Number", "Type", "Coordinate"])
            else :
                writer.writerow(["ID", "Heure", "Chemin Image", "Altitude (m)", "Nombre", "Type", "Coordonnées"])
            writer.writerows(data)
            
        return chemin_complet
    
    def recuperer_mission_par_id(self, mission_id):
        """
        Récupère toutes les infos d'une mission précise.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT chemin_image, coordonnees FROM missions WHERE id = ?", (mission_id,))
        return cursor.fetchone()
    
    def recuperer_mission_par_horodatage(self, horodatage):
        """
        Récupère les détails d'une mission en BDD via son horodatage.
        """
        try:
            cursor = self.conn.cursor()
            query = "SELECT chemin_image, nb_objets, type_objet, coordonnees, altitude FROM missions WHERE horodatage = ?"
            cursor.execute(query, (horodatage,))
            return cursor.fetchone() # Retourne le tuple (chemin, nb, type, coords, alt) ou None
        except Exception as e:
            print(f"Erreur SQL (recuperer_mission) : {e}")
            return None