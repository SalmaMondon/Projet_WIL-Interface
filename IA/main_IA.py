from . import acquisition
from . import postprocessing
from . import preprocessing
from . import stitching
from . import IA_test
import cv2
import time

OUTPUT_IMAGE_PATH = 'IA/output/output_image.jpg'
TEST_IMAGE_PATH   = 'IA/carviewalive.jpg'

# ============================================================
# ÉTAPE 1 — STITCHING
# ============================================================
def stitch_mosaic():
    """Acquire, preprocess and stitch the mosaic. Returns the mosaic as a numpy array."""
    Set = acquisition.acquisition()
    print('Acquisition finished')

    Set = preprocessing.preprocessing(Set)
    print('Preprocessing finished')

    try:
        start_time = time.perf_counter()

        mosaic = stitching.stitching(Set)
        print('Stitching finished')

        mosaic = postprocessing.postprocessing(mosaic)

        ##################### à changer quand on aura les vraies images
        mosaic = cv2.imread(TEST_IMAGE_PATH)
        #####################

        if mosaic is None:
            print(f'[ERROR] Image introuvable : {TEST_IMAGE_PATH}')
            return None

        cv2.imwrite(OUTPUT_IMAGE_PATH, mosaic)
        print(f'Stitching duration: {time.perf_counter() - start_time:.6f} s')
        return mosaic

    except RuntimeError as e:
        print(f'[ERROR] Stitching : {e}')
        return None


# ============================================================
# ÉTAPE 2 — DÉTECTION
# ============================================================
def run_detection(mosaic=None):
    """
    Détecte les objets dans le mosaic (ou dans TEST_IMAGE_PATH par défaut).
    Retourne une liste de tuples (x, y, w, h) en pixels réels.
    """
    if mosaic is None:
        mosaic = cv2.imread(TEST_IMAGE_PATH)
    if mosaic is None:
        print(f'[ERROR] Image introuvable : {TEST_IMAGE_PATH}')
        return []

    h_real, w_real = mosaic.shape[:2]
    print(f'[INFO] Image size : {w_real}x{h_real}')

    try:
        detections = IA_test.detect(mosaic)
        print(f'[INFO] Détections brutes : {len(detections)}')

        coordinates = []
        for d in detections:
            x1, y1, x2, y2 = d['box']
            # Coordonnées normalisées [0,1] → pixels réels
            nx = int(round(x1 * w_real))
            ny = int(round(y1 * h_real))
            nw = int(round((x2 - x1) * w_real))
            nh = int(round((y2 - y1) * h_real))
            if nw > 0 and nh > 0:
                coordinates.append((nx, ny, nw, nh))
                print(f'  box=({nx}, {ny}, {nw}, {nh})  score={d["score"]:.2f}')

        return coordinates

    except Exception as e:
        print(f'[ERROR] Détection : {e}')
        return []


# ============================================================
# PIPELINE COMPLET
# ============================================================
def run_pipeline():
    """Stitching puis détection — appelé par IAWorker."""
    mosaic = stitch_mosaic()
    if mosaic is None:
        return []
    return run_detection(mosaic)