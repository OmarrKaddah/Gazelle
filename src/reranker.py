from FlagEmbedding import FlagReranker
from config import RERANK_MODEL_PATH

_model = None


def getModel():
    global _model
    if _model is None:
        print(f"[reranker] loading from {RERANK_MODEL_PATH}")
        _model = FlagReranker(RERANK_MODEL_PATH, use_fp16=True)
        print(f"[reranker] model ready")
    return _model


def rerank(query, chunks, topK):
    model = getModel()
    pairs = [[query, c['text']] for c in chunks]
    scores = model.compute_score(pairs, normalize=True)
    if not isinstance(scores, list):
        scores = [scores]
    print(f"[DEBUG] rerank: {len(chunks)} candidates -> top {topK}")
    for c, s in zip(chunks, scores):
        print(f"  chunkId={c['chunkId']} rerankScore={s:.4f} pathScore={c.get('score', 0):.4f}")
    ranked = sorted(zip(scores, chunks), key=lambda x: -x[0])[:topK]
    for score, chunk in ranked:
        chunk['rerankScore'] = float(score)
    return [chunk for _, chunk in ranked]
