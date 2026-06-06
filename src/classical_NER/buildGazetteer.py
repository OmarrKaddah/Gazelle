import json
import os
import re
from pathlib import Path

GAZETTEER_THRESHOLD = float(os.environ.get('GAZETTEER_THRESHOLD', '0.75'))


def normalizeArabic(text):
    text = re.sub(r'[ً-ٟ]', '', text)
    text = re.sub(r'[أإآ]', 'ا', text)
    text = re.sub(r'ى', 'ي', text)
    return re.sub(r'\s+', ' ', text).strip()


def loadExtractions():
    all_entities = []
    for p in sorted(Path('extractions').glob('*_entities.json')):
        all_entities.extend(json.loads(p.read_text(encoding='utf-8')))
    return all_entities


def buildGazetteer(entities, threshold):
    seen = {}
    for e in entities:
        score = e.get('score', 0)
        if score < threshold:
            continue
        etype = e.get('type', '').strip()
        raw = e.get('text', '').strip()
        if not etype or not raw:
            continue
        key = (etype, normalizeArabic(raw))
        if key not in seen:
            seen[key] = raw

    gaz = {}
    for (etype, _), surface in seen.items():
        gaz.setdefault(etype, []).append(surface)

    for k in gaz:
        gaz[k] = sorted(set(gaz[k]))

    return gaz


def dumpGazetteer(gaz):
    Path('gazetteer').mkdir(exist_ok=True)
    out = Path('gazetteer/gazetteer.json')
    out.write_text(json.dumps(gaz, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    thresh = GAZETTEER_THRESHOLD
    print(f"threshold={thresh}, scanning extractions/...")

    entities = loadExtractions()
    print(f"got {len(entities)} entity spans")

    gaz = buildGazetteer(entities, thresh)

    for etype, entries in sorted(gaz.items()):
        print(f"  {etype}: {len(entries)} entries")

    total = sum(len(v) for v in gaz.values())
    print(f"total: {total}")

    dumpGazetteer(gaz)
    print("saved to gazetteer/gazetteer.json")
