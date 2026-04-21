import json
import os

CONFIG_FILE = "config.json"

def charger_configuration():
    """
    Charge la langue depuis le JSON, retourne True si 'en', False sinon.
    """
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                return config.get("langue") == "en"
        except Exception:
            return False
    return False

def sauvegarder_configuration(est_anglais):
    """
    Enregistre le choix de langue (booléen) dans le JSON.
    """
    config = {"langue": "en" if est_anglais else "fr"}
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
    except Exception as e:
        print(f"Erreur sauvegarde config: {e}")