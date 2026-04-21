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