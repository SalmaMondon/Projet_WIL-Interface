import sys
import os
from PyQt6.QtCore import QObject, QEvent


class FiltreCurseurLockOn(QObject):
    """
    Classe utilitaire pour changer le curseur au survol d'un widget
    """
    def __init__(self, curseur_hover, parent=None):
        super().__init__(parent)
        self.curseur_hover = curseur_hover

    def eventFilter(self, obj, event):
        # Quand la souris ENTRE dans le widget
        if event.type() == QEvent.Type.Enter:
            obj.setCursor(self.curseur_hover)
            return True # Événement géré

        # Quand la souris SORT du widget (il reprendra le curseur de son parent)
        elif event.type() == QEvent.Type.Leave:
            obj.unsetCursor() # Remet le curseur par défaut
            return True
            
        return super().eventFilter(obj, event)

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