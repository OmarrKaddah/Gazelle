import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'src'))
os.chdir(ROOT)

import json
from pathlib import Path
from retriever import retrieve


K = 5
HOPS = 1
CLEARANCE = 'restricted'  #IMPORTANT: filters fa returnns 0 chunks error


def loadQueries():
    return json.loads(Path('eval/queries.json').read_text(encoding='utf-8'))


def recallAt(retrieved, relevant, k):
    if not relevant:
        return None
    topK = [r['chunkId'] for r in retrieved[:k]]
    hits = sum(1 for c in relevant if c in topK)
    return hits / len(relevant)


def precisionAt(retrieved, relevant, k):
    if not retrieved or not relevant:
        return None
    topK = [r['chunkId'] for r in retrieved[:k]]
    hits = sum(1 for c in topK if c in relevant)
    return hits / k


def reciprocalRank(retrieved, relevant):
    if not relevant:
        return None
    for rank, r in enumerate(retrieved, 1):
        if r['chunkId'] in relevant:
            return 1.0 / rank
    return 0.0


def evalQuery(query):
    out = {'id': query['id'], 'query': query['query'], 'type': query['type'], 'modes': {}}
    for mode in ['vector', 'hybrid', 'graph']:
        retrieved = retrieve(query['query'], mode=mode, k=K, hops=HOPS, clearance=CLEARANCE)
        relevant = query.get('relevantChunks') or []
        out['modes'][mode] = {
            'retrievedIds': [r['chunkId'] for r in retrieved],
            'recallAtK': recallAt(retrieved, relevant, K),
            'precisionAtK': precisionAt(retrieved, relevant, K),
            'mrr': reciprocalRank(retrieved, relevant),
            'count': len(retrieved),
        }
    return out


def avg(values):
    vs = [v for v in values if v is not None]
    return sum(vs) / len(vs) if vs else None


def fmt(v):
    return f"{v:.3f}" if isinstance(v, (int, float)) else "—"


def printReport(results):
    modes = ['vector', 'hybrid', 'graph']
    print("\n" + "=" * 92)
    print(f"{'query':<8} {'type':<12} | " + " | ".join(f"{m:^22}" for m in modes))
    print(f"{'':<8} {'':<12} | " + " | ".join(f"{'R@K  P@K  MRR':^22}" for _ in modes))
    print("-" * 92)
    for r in results:
        cells = []
        for m in modes:
            metrics = r['modes'][m]
            cells.append(f"{fmt(metrics['recallAtK']):>5} {fmt(metrics['precisionAtK']):>5} {fmt(metrics['mrr']):>5}")
        print(f"{r['id']:<8} {r['type']:<12} | " + " | ".join(f"{c:^22}" for c in cells))

    print("-" * 92)
    summaries = []
    for m in modes:
        rs = [r['modes'][m] for r in results]
        summaries.append(
            f"{fmt(avg([x['recallAtK'] for x in rs])):>5} "
            f"{fmt(avg([x['precisionAtK'] for x in rs])):>5} "
            f"{fmt(avg([x['mrr'] for x in rs])):>5}"
        )
    print(f"{'AVG':<8} {'':<12} | " + " | ".join(f"{s:^22}" for s in summaries))

    # Multi-hop only
    multi = [r for r in results if r['type'] == 'multi-hop']
    if multi:
        print("\n--- Multi-hop subset (graph should win) ---")
        for m in modes:
            rs = [r['modes'][m] for r in multi]
            print(f"  {m}: R@K={fmt(avg([x['recallAtK'] for x in rs]))} "
                  f"P@K={fmt(avg([x['precisionAtK'] for x in rs]))} "
                  f"MRR={fmt(avg([x['mrr'] for x in rs]))}")

    print("=" * 92 + "\n")


def main():
    queries = loadQueries()
    annotated = [q for q in queries if q.get('relevantChunks')]
    if not annotated:
        print("No queries have 'relevantChunks' annotated.")
        print("Open eval/queries.json and fill in relevantChunks (list of chunkIds).")
        print("\nDumping retrieved chunkIds for each query so you can pick relevant ones:\n")
        for q in queries:
            for mode in ['vector', 'graph']:
                retrieved = retrieve(q['query'], mode=mode, k=K, hops=HOPS, clearance=CLEARANCE)
                print(f"  [{q['id']} · {mode}] {[r['chunkId'] for r in retrieved[:K]]}")
            print()
        return

    results = [evalQuery(q) for q in annotated]
    Path('eval/results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    printReport(results)
    print(f"Saved: eval/results.json ({len(results)} queries)")


if __name__ == '__main__':
    main()
