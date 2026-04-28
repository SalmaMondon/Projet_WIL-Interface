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
    """Run AI detection on the mosaic. If none provided, loads the test image."""
    if mosaic is None:
        ############
        mosaic = cv2.imread('IA/carviewalive.jpg')
        ############

    try:
        start_time = time.perf_counter()

        detections = IA_test.detect(mosaic)
        print(f"Detections: {len(detections)} car(s)")

        coordinates = []
        for d in detections:
            x1, y1, x2, y2 = d['box']
            x = int(round(x1))
            y = int(round(y1))
            w = int(round(x2 - x1))
            h = int(round(y2 - y1))
            coordinates.append((x, y, w, h))

        detection.pad_to_square(mosaic)
        print("Detection finished")

        end_time = time.perf_counter()
        print(f"Detection duration: {end_time - start_time:.6f} s")

        return coordinates

    except Exception as e:
        print(f'[ERROR] Une erreur est survenue dans le pipeline IA : {e}')
        return []


def run_pipeline():
    """Full pipeline: stitching then detection."""
    mosaic = stitch_mosaic()
    if mosaic is None:
        return []
    return run_detection(mosaic)


print(run_pipeline())