import os
import threading
import numpy as np
import joblib

_ARTIFACT = os.path.join(os.path.dirname(__file__), 'models', 'router.joblib')
_lock = threading.Lock()
_state = {}  # populated lazily: model, threshold, globalIdx


def _load():
    if _state:
        return True
    if not os.path.exists(_ARTIFACT):
        return False
    with _lock:
        if _state:
            return True
        art = joblib.load(_ARTIFACT)
        _state['model'] = art['model']
        _state['threshold'] = art['threshold']
        _state['globalIdx'] = art.get('globalIdx', 1)
    return True


def routeQuery(query, backend='ollama'):
    if _load():
        from embedding import embedNanSafe
        emb = np.asarray(embedNanSafe(query), dtype=np.float32).reshape(1, -1)
        prob = _state['model'].predict_proba(emb)[0, _state['globalIdx']]
        return 'global' if prob >= _state['threshold'] else 'local'

    # fallback: LLM classifier (used before the model has been trained)
    import json
    from llmTriples import callLLM
    PROMPT = (
        'Classify the question by the scope of evidence it needs.\n'
        '- "global": needs an understanding of the corpus as a whole — themes, trends,\n'
        '  patterns, comparisons, or a summary ("main", "overall", "across the documents").\n'
        '- "local": answerable from a specific fact, entity, number, date, or passage.\n\n'
        'Return JSON only: {{"scope": "global"}} or {{"scope": "local"}}.\n\n'
        'Question: "{query}"'
    )
    raw = callLLM(PROMPT.format(query=query), backend=backend)
    return json.loads(raw)['scope']
