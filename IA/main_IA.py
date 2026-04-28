from . import acquisition
from . import detection
from . import postprocessing
from . import preprocessing
from . import stitching
from . import IA_test
import cv2
import time


def stitch_mosaic():
    """Acquire, preprocess and stitch the mosaic."""
    Set = acquisition.acquisition()
    print('Acquisition finished')

    Set = preprocessing.preprocessing(Set)
    print('Preprocessing finished')
    try :
        start_time = time.perf_counter()

        mosaic = stitching.stitching(Set)
        print('Stitching finished')

        mosaic = postprocessing.postprocessing(mosaic)
        cv2.imwrite('output/output_image.jpg', mosaic)

        end_time = time.perf_counter()
        print(f"Stitching duration: {end_time - start_time:.6f} s")

        return mosaic

    except RuntimeError as e:
        print(f'[ERROR] {e}')
        return None


def run_detection(mosaic=None):
    if mosaic is None:
        mosaic = cv2.imread('IA/carviewalive.jpg')
    if mosaic is None: return []

    h_real, w_real = mosaic.shape[:2] # 1830, 3771

    try:
        # detections contient maintenant des boxes entre 0 et 1
        detections = IA_test.detect(mosaic)
        
        coordinates = []
        for d in detections:
            x1_norm, y1_norm, x2_norm, y2_norm = d['box']
            
            # On multiplie directement par la taille réelle en pixels
            nx = int(round(x1_norm * w_real))
            ny = int(round(y1_norm * h_real))
            nw = int(round((x2_norm - x1_norm) * w_real))
            nh = int(round((y2_norm - y1_norm) * h_real))
            
            coordinates.append((nx, ny, nw, nh))

        return coordinates
    except Exception as e:
        print(f"Erreur : {e}")
        return []


def run_pipeline():
    """Full pipeline: stitching then detection."""
    mosaic = stitch_mosaic()
    if mosaic is None:
        return []
    return run_detection()


print(run_detection())