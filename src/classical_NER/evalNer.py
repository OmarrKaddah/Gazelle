import json
import sys
from pathlib import Path


def loadGold(docName):
    path = Path(f'annotations/gold_{docName}.json')
    return json.loads(path.read_text(encoding='utf-8'))


def loadCrf(docName, modelName):
    path = Path(f'extractions/{docName}_{modelName}_entities.json')
    return json.loads(path.read_text(encoding='utf-8'))


def loadGliner(docName):
    path = Path(f'extractions/{docName}_entities.json')
    return json.loads(path.read_text(encoding='utf-8'))


def toSpanSet(entities):
    return {(e['chunkId'], e['start'], e['end']) for e in entities}


def computeF1(gold, pred):
    tp = len(gold & pred)
    fp = len(pred - gold)
    fn = len(gold - pred)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1, tp, fp, fn


def printReport(name, goldList, predList):
    goldSet = toSpanSet(goldList)
    predSet = toSpanSet(predList)
    p, r, f1, tp, fp, fn = computeF1(goldSet, predSet)

    print(f"\n{name}")
    print(f"  P={p:.4f}  R={r:.4f}  F1={f1:.4f}  support={len(goldSet)}")
    print(f"  gold={len(goldSet)}  pred={len(predSet)}  TP={tp}  FP={fp}  FN={fn}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("usage: python evalNer.py <docName> [--model=NAME] [--gliner]")
        print("  example: python evalNer.py wikiann_test --model=crf_bank")
        print("  example: python evalNer.py wikiann_test --gliner")
        print("  example: python evalNer.py wikiann_test --model=crf_combined --gliner")
        sys.exit(1)

    docName   = sys.argv[1]
    modelArgs = [a for a in sys.argv if a.startswith('--model=')]
    modelName = modelArgs[0].split('=', 1)[1] if modelArgs else None
    runGliner = '--gliner' in sys.argv

    print(f"loading gold from annotations/gold_{docName}.json")
    gold = loadGold(docName)
    print(f"{len(gold)} gold spans")

    if modelName:
        print(f"loading {modelName} predictions")
        crf_pred = loadCrf(docName, modelName)
        printReport(f"{modelName}  —  {docName}", gold, crf_pred)

    if runGliner:
        print(f"loading GLiNER predictions")
        gliner_pred = loadGliner(docName)
        printReport(f"GLiNER  —  {docName}", gold, gliner_pred)
