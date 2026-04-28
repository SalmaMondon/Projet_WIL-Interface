from . import acquisition
from . import detection
from . import postprocessing
from . import preprocessing
from . import stitching
from . import IA_test
import cv2
import time

def fonction_ia():
    # 1. Pipeline de traitement d'images
    try:
        data_set = acquisition.acquisition()
        print('Acquisition finished')

        data_set = preprocessing.preprocessing(data_set)
        print('Preprocessing finished')

        start_time = time.perf_counter()
        
        # Génération de la mosaïque
        mosaique = stitching.stitching(data_set)
        print('Assemblage finished')

        mosaique = postprocessing.postprocessing(mosaique)
        
        # --- POINT CRUCIAL : Dimensions réelles ---
        # On récupère la taille de l'image de sortie (ex: 1920x1080)
        # avant que l'IA ne la réduise en interne (ex: 640x640)
        h_reel, w_reel = mosaique.shape[:2]
        
        # Sauvegarde pour l'interface
        cv2.imwrite('output/output_image.jpg', mosaique)

        # 2. Détection IA
        # Note : On utilise l'image chargée ou la mosaïque générée
        img_ia = cv2.imread('IA/carviewalive.jpg')
        if img_ia is None:
            img_ia = mosaique # Fallback si le fichier test n'existe pas
            
        # Appel de la détection (renvoie la liste filtrée par NMS)
        detections = IA_test.detect(img_ia)
        print(f"Détections (après NMS) : {len(detections)} objet(s)")

        # 3. Calcul des Ratios (Scaling)
        # On définit la taille d'entrée que l'IA utilise en interne
        # Doit correspondre à la variable IMG_SIZE dans ton script IA_test
        IMG_SIZE_IA = 640  # Modifie cette valeur si Maël utilise 448 ou autre
        
        ratio_w = w_reel / IMG_SIZE_IA
        ratio_h = h_reel / IMG_SIZE_IA

        coordonnees = []
        for d in detections:
            # Extraction des coins fournis par l'IA (format x1, y1, x2, y2)
            x1, y1, x2, y2 = d['box']
            
            # Application du ratio + conversion en (x, y, w, h) pour PyQt
            # On multiplie par le ratio pour "étirer" la boîte à la taille réelle
            x = int(round(x1 * ratio_w))
            y = int(round(y1 * ratio_h))
            w = int(round((x2 - x1) * ratio_w))
            h = int(round((y2 - y1) * ratio_h))
            
            coordonnees.append((x, y, w, h))

        # Finalisation
        detection.pad_to_square(mosaique) # Si requis par ton pipeline
        
        end_time = time.perf_counter()
        print(f"Full process finished in {end_time - start_time:.4f} s")
        
        return coordonnees

    except Exception as e:
        print(f'[ERROR] Une erreur est survenue dans le pipeline IA : {e}')
        return []

print(fonction_ia())