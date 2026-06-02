import json
import sys
from pathlib import Path
from collections import defaultdict


def loadGold(docName):
    path = Path(f'annotations/gold_{docName}.json')
    return json.loads(path.read_text(encoding='utf-8'))


def loadCrf(docName):
    path = Path(f'extractions/crf/{docName}_crf_entities.json')
    return json.loads(path.read_text(encoding='utf-8'))


def loadGliner(docName):
    path = Path(f'extractions/{docName}_entities.json')
    return json.loads(path.read_text(encoding='utf-8'))


def toSpanSet(entities):
    return {(e['chunkId'], e['start'], e['end'], e['type']) for e in entities}


def computeF1(gold, pred):
    tp = len(gold & pred)
    fp = len(pred - gold)
    fn = len(gold - pred)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1, tp, fp, fn


def computePerType(goldList, predList):
    goldByType = defaultdict(set)
    predByType = defaultdict(set)
    for e in goldList:
        goldByType[e['type']].add((e['chunkId'], e['start'], e['end'], e['type']))
    for e in predList:
        predByType[e['type']].add((e['chunkId'], e['start'], e['end'], e['type']))

    types = sorted(set(goldByType) | set(predByType))
    return types, goldByType, predByType


def printReport(name, goldList, predList):
    goldTypes = {e['type'] for e in goldList}
    predList  = [e for e in predList if e['type'] in goldTypes]

    goldSet = toSpanSet(goldList)
    predSet = toSpanSet(predList)

    types, goldByType, predByType = computePerType(goldList, predList)

    print(f"\n{'='*55}")
    print(f"  {name}")
    print(f"{'='*55}")
    print(f"  {'Type':<22} {'P':>7} {'R':>7} {'F1':>7} {'Support':>9}")
    print(f"  {'-'*54}")

    for t in types:
        p, r, f1, tp, fp, fn = computeF1(goldByType[t], predByType[t])
        support = len(goldByType[t])
        print(f"  {t:<22} {p:>7.4f} {r:>7.4f} {f1:>7.4f} {support:>9}")

    print(f"  {'-'*54}")
    p, r, f1, tp, fp, fn = computeF1(goldSet, predSet)
    print(f"  {'micro avg':<22} {p:>7.4f} {r:>7.4f} {f1:>7.4f} {len(goldSet):>9}")
    print(f"  gold spans: {len(goldSet)}  predicted: {len(predSet)}  TP: {tp}  FP: {fp}  FN: {fn}")
    print(f"  (predictions filtered to gold types only: {sorted(goldTypes)})")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("usage: python evalNer.py <docName> [crf|gliner|both]")
        print("  example: python evalNer.py anercorp_test both")
        sys.exit(1)

    docName = sys.argv[1]
    mode    = sys.argv[2] if len(sys.argv) >= 3 else 'both'

    print(f"[evalNer] loading gold from annotations/gold_{docName}.json")
    gold = loadGold(docName)
    print(f"[evalNer] {len(gold)} gold spans")

    if mode in ('crf', 'both'):
        print(f"[evalNer] loading CRF predictions from extractions/crf/{docName}_crf_entities.json")
        crf_pred = loadCrf(docName)
        printReport(f"CRF  —  {docName}", gold, crf_pred)

    if mode in ('gliner', 'both'):
        print(f"[evalNer] loading GLiNER predictions from extractions/{docName}_entities.json")
        gliner_pred = loadGliner(docName)
        printReport(f"GLiNER  —  {docName}", gold, gliner_pred)

