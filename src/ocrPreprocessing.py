from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

import cv2
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier

from config import (
    HANDWRITING_PATCHES_PER_IMAGE,
    HANDWRITING_PATCH_SIZE,
    HANDWRITING_PATCH_STRIDE,
    HANDWRITING_MODEL_PATH,
    HANDWRITING_THRESHOLD,
)

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp'}


@dataclass
class HandwritingRemovalModel:
    classifier: RandomForestClassifier
    patchSize: int
    stride: int
    threshold: float


def collectImagePaths(folderPath):
    folder = Path(folderPath)
    return sorted(path for path in folder.rglob('*') if path.suffix.lower() in IMAGE_EXTENSIONS)


def loadGrayImage(imagePath):
    image = cv2.imread(str(imagePath), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(str(imagePath))
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def buildHogDescriptor(patchSize):
    blockSize = (patchSize // 2, patchSize // 2)
    blockStride = (patchSize // 4, patchSize // 4)
    cellSize = (patchSize // 4, patchSize // 4)
    return cv2.HOGDescriptor((patchSize, patchSize), blockSize, blockStride, cellSize, 9)


def padImage(image, patchSize):
    height, width = image.shape[:2]
    padBottom = max(0, patchSize - height)
    padRight = max(0, patchSize - width)
    if padBottom == 0 and padRight == 0:
        return image
    return cv2.copyMakeBorder(image, 0, padBottom, 0, padRight, cv2.BORDER_REFLECT)


def windowPositions(length, windowSize, stride):
    if length <= windowSize:
        return [0]
    positions = list(range(0, length - windowSize + 1, stride))
    last = length - windowSize
    if positions[-1] != last:
        positions.append(last)
    return positions


def extractPatchFeatures(patch, hogDescriptor):
    resized = cv2.resize(patch, hogDescriptor.winSize, interpolation=cv2.INTER_AREA)
    floatPatch = resized.astype(np.float32) / 255.0
    hogFeatures = hogDescriptor.compute(resized).reshape(-1)

    inkMask = cv2.adaptiveThreshold(
        resized,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        17,
        11,
    )
    edgeMask = cv2.Canny(resized, 40, 120)
    sobelX = cv2.Sobel(floatPatch, cv2.CV_32F, 1, 0, ksize=3)
    sobelY = cv2.Sobel(floatPatch, cv2.CV_32F, 0, 1, ksize=3)
    gradient = np.hypot(sobelX, sobelY)
    histogram = cv2.calcHist([resized], [0], None, [16], [0, 256]).flatten()
    histogram = histogram / max(histogram.sum(), 1.0)
    histogram = np.clip(histogram, 1e-8, 1.0)

    components = cv2.connectedComponents(inkMask)[0] - 1
    foregroundRatio = float(np.mean(inkMask > 0))
    edgeDensity = float(np.mean(edgeMask > 0))
    horizontalProjection = inkMask.sum(axis=1).astype(np.float32)
    verticalProjection = inkMask.sum(axis=0).astype(np.float32)

    scalarFeatures = np.array(
        [
            float(floatPatch.mean()),
            float(floatPatch.std()),
            float(np.median(floatPatch)),
            float(np.percentile(floatPatch, 10)),
            float(np.percentile(floatPatch, 90)),
            foregroundRatio,
            edgeDensity,
            float(cv2.Laplacian(floatPatch, cv2.CV_32F).var()),
            float(gradient.mean()),
            float(gradient.std()),
            float(components),
            float(horizontalProjection.var()),
            float(verticalProjection.var()),
        ],
        dtype=np.float32,
    )
    return np.concatenate([hogFeatures.astype(np.float32), scalarFeatures, histogram.astype(np.float32)])


def sampleTrainingPatches(image, label, patchSize, patchesPerImage, hogDescriptor, randomState):
    rng = np.random.default_rng(randomState)
    padded = padImage(image, patchSize)
    height, width = padded.shape[:2]
    maxY = height - patchSize
    maxX = width - patchSize
    features = []
    labels = []
    for _ in range(patchesPerImage):
        y = int(rng.integers(0, maxY + 1))
        x = int(rng.integers(0, maxX + 1))
        patch = padded[y : y + patchSize, x : x + patchSize]
        features.append(extractPatchFeatures(patch, hogDescriptor))
        labels.append(label)
    return features, labels


def buildTrainingSet(handwrittenPaths, cleanPaths, patchSize, patchesPerImage, randomState):
    hogDescriptor = buildHogDescriptor(patchSize)      
    features = []      
    labels = []
    for index, imagePath in enumerate(handwrittenPaths):          
        image = loadGrayImage(imagePath)         
        sampledFeatures, sampledLabels = sampleTrainingPatches(
            image,
            1,
            patchSize,
            patchesPerImage,
            hogDescriptor,
            randomState + index,
        )
        features.extend(sampledFeatures)
        labels.extend(sampledLabels)
    for index, imagePath in enumerate(cleanPaths):
        image = loadGrayImage(imagePath)
        sampledFeatures, sampledLabels = sampleTrainingPatches(
            image,              
            0,
            patchSize,
            patchesPerImage,
            hogDescriptor,
            randomState + 10000 + index,
        )
        features.extend(sampledFeatures)
        labels.extend(sampledLabels)
    return np.asarray(features, dtype=np.float32), np.asarray(labels, dtype=np.int32)


def trainHandwritingRemovalModel(handwrittenDir, cleanDir, modelPath, patchSize=HANDWRITING_PATCH_SIZE, stride=HANDWRITING_PATCH_STRIDE, patchesPerImage=HANDWRITING_PATCHES_PER_IMAGE, randomState=42):
    handwrittenPaths = collectImagePaths(handwrittenDir)
    cleanPaths = collectImagePaths(cleanDir)
    features, labels = buildTrainingSet(handwrittenPaths, cleanPaths, patchSize, patchesPerImage, randomState)
    classifier = RandomForestClassifier(
        n_estimators=400,
        class_weight='balanced_subsample',
        n_jobs=-1,
        random_state=randomState,
    )
    classifier.fit(features, labels)
    model = HandwritingRemovalModel(
        classifier=classifier,
        patchSize=patchSize,       
        stride=stride,
        threshold=HANDWRITING_THRESHOLD,
    )
    modelFile = Path(modelPath)
    modelFile.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, modelFile)
    return str(modelFile)


def loadHandwritingRemovalModel(modelPath):
    model = joblib.load(modelPath)
    if isinstance(model, HandwritingRemovalModel):
        return model
    return HandwritingRemovalModel(**model)


def predictHandwritingScoreMap(image, model):     
    grayscale = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    padded = padImage(grayscale, model.patchSize)
    hogDescriptor = buildHogDescriptor(model.patchSize)
    height, width = padded.shape[:2]
    yPositions = windowPositions(height, model.patchSize, model.stride)
    xPositions = windowPositions(width, model.patchSize, model.stride)

    positiveIndex = int(np.where(model.classifier.classes_ == 1)[0][0])

    patchPositions = []
    patchFeatures = []      
    for y in yPositions:
        for x in xPositions:
            patch = padded[y : y + model.patchSize, x : x + model.patchSize]
            patchPositions.append((y, x))


            patchFeatures.append(extractPatchFeatures(patch, hogDescriptor))

    featureMatrix = np.asarray(patchFeatures, dtype=np.float32)
    scores = model.classifier.predict_proba(featureMatrix)[:, positiveIndex]

    scoreMap = np.zeros((height, width), dtype=np.float32)
    
    weightMap = np.zeros((height, width), dtype=np.float32)

    for index, (y, x) in enumerate(patchPositions):
       
        score = float(scores[index])
       
        scoreMap[y : y + model.patchSize, x : x + model.patchSize] += score
        weightMap[y : y + model.patchSize, x : x + model.patchSize] += 1.0

    scoreMap = scoreMap / np.maximum(weightMap, 1.0)
    scoreMap = cv2.GaussianBlur(scoreMap, (0, 0), sigmaX=max(1, model.patchSize // 4))
    return scoreMap[: grayscale.shape[0], : grayscale.shape[1]]


def buildHandwritingMask(scoreMap, threshold):
    mask = (scoreMap >= threshold).astype(np.uint8) * 255
    return mask


def removeHandwriting(imagePath, modelPath=None):
    image = cv2.imread(str(imagePath), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(str(imagePath))
    if modelPath is None:
        modelPath = HANDWRITING_MODEL_PATH
    model = loadHandwritingRemovalModel(modelPath)
    scoreMap = predictHandwritingScoreMap(image, model)
    mask = buildHandwritingMask(scoreMap, model.threshold)
    return cv2.inpaint(image, mask, 3, cv2.INPAINT_TELEA)


def preprocessImageFile(imagePath, outputPath=None, modelPath=None):
    if modelPath is None:
        modelPath = HANDWRITING_MODEL_PATH
    cleaned = removeHandwriting(imagePath, modelPath)
    if outputPath is None:
        handle = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        outputPath = handle.name
        handle.close()
    cv2.imwrite(str(outputPath), cleaned)
    return str(outputPath)