import _bootstrap  # noqa: F401
import sys
from retriever import retrieve

query = sys.argv[1] if len(sys.argv) > 1 else "ما هي شروط إلغاء ترخيص البنك"
mode = sys.argv[2] if len(sys.argv) > 2 else "vector"
k = int(sys.argv[3]) if len(sys.argv) > 3 else 5
hops = int(sys.argv[4]) if len(sys.argv) > 4 else 1

print(f"\nquery: {query}\nmode: {mode}  k={k}  hops={hops}\n" + "=" * 60)
results = retrieve(query, mode=mode, k=k, hops=hops, clearance='restricted')
for r in results:
    score = r.get('score')
    scoreStr = f"{score:.4f}" if isinstance(score, (int, float)) else "—"
    section = ' > '.join(r.get('sectionPath') or [])
    print(f"\n[{r.get('source', '?')}] {r['chunkId']}  score={scoreStr}")
    print(f"  section: {section}")
    print(f"  pages:   {r.get('pages')}")
    print(f"  text:    {r['text'][:200].strip()}...")
print(f"\n{len(results)} results")
