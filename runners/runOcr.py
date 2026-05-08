import _bootstrap  # noqa: F401
from ocr import runOcrAndDump

imagePath = "Documents/chapter_3.pdf"

mdPath, sidecarPath = runOcrAndDump(imagePath)
print(f"Saved: {mdPath}")
print(f"Saved: {sidecarPath}")
