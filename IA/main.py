import config
import acquisition
import detection
import postprocessing
import preprocessing
import stitching
import IA
import cv2
import time

def fonction_ia():
    Set = acquisition.acquisition()
    print('acquisition finished')

    Set = preprocessing.preprocessing(Set)
    print('preprocessing finished')

    try:
        start_time = time.perf_counter()
        mosaique = stitching.stitching(Set)
        print('assemblage finished')

        mosaique = postprocessing.postprocessing(mosaique)
        cv2.imwrite('output/output_image.jpg', mosaique)

        # Détection IA sur la mosaïque finale
        ############
        mosaique = cv2.imread('IA/carviewalive.jpg')
        ############
        detections = IA.detect(mosaique)
        print(f"Détections : {len(detections)} voiture(s)")
        coordonnees = []
        for d in detections:
            # On récupère x1, y1, x2, y2
            x1, y1, x2, y2 = d['box']
            
            # Ton interface a besoin de (x, y, largeur, hauteur)
            # On calcule : largeur = x2 - x1 et hauteur = y2 - y1
            x = int(round(x1))
            y = int(round(y1))
            w = int(round(x2 - x1))
            h = int(round(y2 - y1))
            
            coordonnees.append((x, y, w, h))  

        detection.pad_to_square(mosaique)
        print("Full process finished")

        end_time = time.perf_counter()
        print(f"Duration : {end_time - start_time:.6f} s")
        return coordonnees

    except RuntimeError as e:
        print(f'[ERROR] {e}')
        return []

print(fonction_ia())