import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import json
import re
from pathlib import Path

GAZETTEER_THRESHOLD = float(os.environ.get('GAZETTEER_THRESHOLD', '0.75'))


def normalizeArabic(text):
    text = re.sub(r'[ً-ٟ]', '', text)
    text = re.sub(r'[أإآ]', 'ا', text)
    text = re.sub(r'ى', 'ي', text)
    return re.sub(r'\s+', ' ', text).strip()


def loadExtractions():
    entities = []
    for path in sorted(Path('extractions').glob('*_entities.json')):
        entities.extend(json.loads(path.read_text(encoding='utf-8')))
    return entities


def buildGazetteer(entities, threshold):
    seen = {}
    for e in entities:
        if e.get('score', 0) < threshold:
            continue
        etype = e.get('type', '').strip()
        text = e.get('text', '').strip()
        if not etype or not text:
            continue
        key = (etype, normalizeArabic(text))
        if key not in seen:
            seen[key] = text
    gazetteer = {}
    for (etype, _), surface in seen.items():
        gazetteer.setdefault(etype, []).append(surface)
    for etype in gazetteer:
        gazetteer[etype] = sorted(set(gazetteer[etype]))
    return gazetteer


def dumpGazetteer(gazetteer):
    Path('gazetteer').mkdir(exist_ok=True)
    Path('gazetteer/gazetteer.json').write_text(
        json.dumps(gazetteer, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


if __name__ == '__main__':
    print(f"Loading extractions (threshold={GAZETTEER_THRESHOLD})...")
    entities = loadExtractions()
    print(f"Total entities loaded: {len(entities)}")

    gazetteer = buildGazetteer(entities, GAZETTEER_THRESHOLD)

    total = sum(len(v) for v in gazetteer.values())
    for etype, entries in sorted(gazetteer.items()):
        print(f"  {etype}: {len(entries)} entries")
    print(f"Total unique entries: {total}")

    dumpGazetteer(gazetteer)
    print("Saved -> gazetteer/gazetteer.json")
