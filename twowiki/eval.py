import _bootstrap  # noqa: F401
import json
import time
from collections import defaultdict
from pathlib import Path
from retrieve import RetrievalIndex
from khop import KhopIndex
from loadChunks import chunkId, paragraphText, DEV, LIMIT


# ── version + config for this run ────────────────────────────────
VERSION = 'v8'
LABEL = 'route2related_2wiki'
NOTES = 'Route 2 graph (OpenRouter LLM extraction -> RELATED {predicate,description,weight}) retrieved by PPR on 2WikiMultiHopQA. Default layers: RELATED + SYNONYM. co-mention and bare triples OFF. Same knobs as the musique v8 run (alpha=0.5, seedTopK=5, synonymWeight=1.0).'
CONFIG = {
    'retriever': 'ppr',
    'pprAlpha': 0.5,
    'seedTopK': 5,
    'relatedEdges': True,
    'entityAlignment': True,
    'synonymWeight': 1.0,
    'coMentionEdges': False,
    'tripleEdges': False,
    'nodeSpecificity': False,
}
# ─────────────────────────────────────────────────────────────────


K_VALUES = (1, 2, 5, 10)
TOPK = max(K_VALUES)
OUT_DIR = Path(__file__).parent / 'eval_results'
OUT = OUT_DIR / f'{VERSION}_{LABEL}.json'


def loadGold():
    rows = json.loads(DEV.read_text(encoding='utf-8'))
    rows = rows if LIMIT is None else rows[:LIMIT]
    gold = []
    for ex in rows:
        supTitles = {t for t, _ in ex.get('supporting_facts', [])}
        goldIds = set()
        for title, sentences in ex.get('context', []):
            if title in supTitles:
                text = paragraphText(sentences)
                if text:
                    goldIds.add(chunkId(text))
        gold.append({
            'id': ex['_id'],
            'question': ex['question'],
            'hop': ex.get('type', 'unknown'),
            'goldChunkIds': sorted(goldIds),
            'answer': ex.get('answer'),
        })
    return gold


def scoreOne(retrievedIds, goldIds):
    goldSet = set(goldIds)
    nGold = len(goldSet)
    out = {}
    for k in K_VALUES:
        topK = set(retrievedIds[:k])
        hits = len(topK & goldSet)
        out[f'recall@{k}'] = hits / nGold if nGold else 0.0
        out[f'hit@{k}'] = 1.0 if hits > 0 else 0.0
    return out


def aggregate(perQuestion):
    if not perQuestion:
        return {}
    keys = [f'{m}@{k}' for k in K_VALUES for m in ('recall', 'hit')]
    return {k: sum(q['metrics'][k] for q in perQuestion) / len(perQuestion) for k in keys}


def printBlock(label, metrics, n):
    print(f'{label} (n={n}):')
    recallLine = '  ' + '   '.join(f'recall@{k} = {metrics[f"recall@{k}"]:.3f}' for k in K_VALUES)
    hitLine = '  ' + '   '.join(f'hit@{k}    = {metrics[f"hit@{k}"]:.3f}' for k in K_VALUES)
    print(recallLine)
    print(hitLine)


def main():
    OUT_DIR.mkdir(exist_ok=True)
    print(f'[eval] {VERSION}_{LABEL}  ({NOTES})')
    print(f'[eval] config: {CONFIG}')
    print(f'[eval] 2wiki dev (LIMIT={LIMIT})')
    gold = loadGold()
    print(f'[eval] {len(gold)} questions loaded')
    print(f'[eval] building index...')
    if CONFIG.get('retriever') == 'khop':
        index = KhopIndex('2wiki', depth=CONFIG['khopDepth'])
    else:
        index = RetrievalIndex(
            '2wiki',
            entityAlignment=CONFIG['entityAlignment'],
            synonymWeight=CONFIG['synonymWeight'],
            coMentionEdges=CONFIG['coMentionEdges'],
            tripleEdges=CONFIG['tripleEdges'],
            relatedEdges=CONFIG.get('relatedEdges', False),
        )

    print(f'[eval] running retrieval...')
    t0 = time.time()
    perQuestion = []
    skipped = []
    for i, g in enumerate(gold, 1):
        try:
            _, chunks = index.retrieve(
                g['question'],
                topK=TOPK,
                alpha=CONFIG.get('pprAlpha', 0.5),
                seedTopK=CONFIG.get('seedTopK', 5),
                nodeSpecificity=CONFIG.get('nodeSpecificity', False),
            )
        except RuntimeError as e:
            print(f'  [skip] {g["id"]}: {str(e)[:120]}')
            skipped.append({'id': g['id'], 'question': g['question'], 'error': str(e)[:300]})
            continue
        retrievedIds = [c['chunkId'] for c in chunks]
        metrics = scoreOne(retrievedIds, g['goldChunkIds'])
        perQuestion.append({
            'id': g['id'],
            'hop': g['hop'],
            'question': g['question'],
            'answer': g['answer'],
            'goldChunkIds': g['goldChunkIds'],
            'retrievedChunkIds': retrievedIds,
            'metrics': metrics,
        })
        if i % 25 == 0:
            print(f'  {i}/{len(gold)}')
    elapsed = time.time() - t0
    print(f'[eval] done in {elapsed:.1f}s ({elapsed/len(gold)*1000:.0f} ms/query)')
    print()

    overall = aggregate(perQuestion)
    printBlock('aggregate', overall, len(perQuestion))
    print()

    byHop = defaultdict(list)
    for q in perQuestion:
        byHop[q['hop']].append(q)
    print('by question type:')
    for hop in sorted(byHop):
        printBlock(f'  {hop}', aggregate(byHop[hop]), len(byHop[hop]))

    if skipped:
        print()
        print(f'[eval] {len(skipped)} questions skipped due to embed failure')

    OUT.write_text(json.dumps({
        'version': VERSION,
        'label': LABEL,
        'notes': NOTES,
        'config': CONFIG,
        'aggregate': overall,
        'byHop': {h: aggregate(qs) for h, qs in byHop.items()},
        'perQuestion': perQuestion,
        'skipped': skipped,
    }, indent=2), encoding='utf-8')
    print()
    print(f'[eval] results written to {OUT}')


if __name__ == '__main__':
    main()
