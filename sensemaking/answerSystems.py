import _bootstrap  # noqa: F401
import sys
import json
from pathlib import Path
from globalSearch import globalSearch
from baseline import vectorAnswer
from config import GRAPH_EXTRACT_BACKEND

# Bridge between AutoQ (questions) and AutoE (judging): run both systems over the
# questions and write one answer file per condition in the schema AutoE merges on —
# a JSON list of {question_id, question_text, answer}. AutoE pairwise-scores then
# compares these two files. Resume-safe: re-running skips already-answered questions.
#
# Usage: python sensemaking/answerSystems.py <questionsJson> [corpus] [outDir]

CORPUS = sys.argv[2] if len(sys.argv) > 2 else 'apnews'
OUT_DIR = Path(sys.argv[3] if len(sys.argv) > 3 else 'sensemaking/eval_results')


def loadQuestions(path):
    raw = json.loads(Path(path).read_text(encoding='utf-8'))
    rows = raw['questions'] if isinstance(raw, dict) else raw
    return [{'question_id': q.get('id', q.get('question_id')),
             'question_text': q.get('text', q.get('question_text'))} for q in rows]


def loadDone(path):
    if not path.exists():
        return {}
    return {r['question_id']: r for r in json.loads(path.read_text(encoding='utf-8'))}


def generate(questions, answerFn, path):
    done = loadDone(path)
    out = list(done.values())
    for i, q in enumerate(questions, 1):
        if q['question_id'] in done:
            continue
        answer = answerFn(q['question_text'])
        out.append({**q, 'answer': answer})
        path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'  {i}/{len(questions)} {q["question_id"]}', flush=True)
    return out


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    questions = loadQuestions(sys.argv[1])
    print(f'[answerSystems] {len(questions)} questions, corpus={CORPUS}, backend={GRAPH_EXTRACT_BACKEND}')
    print('[answerSystems] global arm...')
    generate(questions, lambda qt: globalSearch(qt, CORPUS, backend=GRAPH_EXTRACT_BACKEND),
             OUT_DIR / 'global_answers.json')
    print('[answerSystems] vector baseline...')
    generate(questions, lambda qt: vectorAnswer(qt, CORPUS, backend=GRAPH_EXTRACT_BACKEND),
             OUT_DIR / 'vector_answers.json')
    print(f'[answerSystems] wrote global_answers.json + vector_answers.json to {OUT_DIR}')


if __name__ == '__main__':
    main()
