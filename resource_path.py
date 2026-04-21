import sys
import os

def resource_path(relative_path):
        """ 
        Calcule le chemin absolu vers la ressource, compatible PyInstaller

        Entrée :
            relative_path (str) : chemin relatif
        """
        # Si l'app est lancée via le .exe, sys._MEIPASS pointe vers le dossier de l'app (qui inclut _internal)
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        
        # Pour les versions récentes de PyInstaller en mode --onedir :
        # Si le dossier n'est pas trouvé à la racine, on tente dans _internal
        path_normal = os.path.join(base_path, relative_path)
        if not os.path.exists(path_normal):
            path_internal = os.path.join(base_path, "_internal", relative_path)
            if os.path.exists(path_internal):
                return path_internal
                
        return path_normal