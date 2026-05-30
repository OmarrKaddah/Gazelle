import _bootstrap  # noqa: F401
import os
from pathlib import Path

from ocrPreprocessing import trainHandwritingRemovalModel

HANDWRITTEN_DIR = Path(os.environ.get('HANDWRITTEN_DIR', 'ocr_dataset/Historical Arabic Handwritten Text Recognition Dataset'))
CLEAN_DIR = Path(os.environ.get('CLEAN_DIR', 'Documents'))
MODEL_PATH = Path(os.environ.get('HANDWRITING_MODEL_PATH', 'models/handwriting_removal.joblib'))

savedPath = trainHandwritingRemovalModel(
    str(HANDWRITTEN_DIR),
    str(CLEAN_DIR),
    str(MODEL_PATH),
)
print(savedPath)