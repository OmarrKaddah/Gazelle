import _bootstrap  # noqa: F401
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def buildSnippet(strategy, docName):


    if strategy == 'llm':

        entityModule = 'llmNER'

    else:
        entityModule = 'glinerExtract'

    return f"""
import json
import time
from {entityModule} import extractEntities
from typedOntologyExtract import extractDoc

docName = {docName!r}

entityStart = time.perf_counter()
entities = extractEntities(docName)
entitySeconds = time.perf_counter() - entityStart

relationshipStart = time.perf_counter()
relations = extractDoc(docName)
relationshipSeconds = time.perf_counter() - relationshipStart

print(json.dumps({{
    'docName': docName,
    'strategy': {strategy!r},
    'entityCount': len(entities),
    'relationshipCount': sum(len(r.get('relationships', [])) for r in relations),
    'entitySeconds': entitySeconds,
    'relationshipSeconds': relationshipSeconds,
    'totalSeconds': entitySeconds + relationshipSeconds,
}}, ensure_ascii=False))
"""



def runStrategy(strategy, docName, env):
    
    snippet = buildSnippet(strategy, docName)
    completed = subprocess.run(
        [sys.executable, '-c', snippet],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{strategy} failed for {docName}:\n{completed.stdout}\n{completed.stderr}"
        )
    return json.loads(completed.stdout.strip())


def printTable(rows):
    headers = ['docName', 'strategy', 'entityCount', 'relationshipCount', 'entitySeconds', 'relationshipSeconds', 'totalSeconds']
    widths = {h: len(h) for h in headers}
    for row in rows:
        for h in headers:
            widths[h] = max(widths[h], len(str(row[h])))

    headerLine = ' | '.join(h.ljust(widths[h]) for h in headers)
    separator = '-+-'.join('-' * widths[h] for h in headers)
    print(headerLine)
    print(separator)
    for row in rows:
        print(' | '.join(str(row[h]).ljust(widths[h]) for h in headers))


def main():
    parser = argparse.ArgumentParser(description='Benchmark entity extraction strategies on chunk files')
    parser.add_argument('docName', nargs='+', help='Document name(s) with chunks/<docName>.json already generated')
    parser.add_argument('--strategies', nargs='+', default=['gliner', 'llm', 'hybrid'], choices=['gliner', 'llm', 'hybrid'])
    parser.add_argument('--output', default=None, help='Optional JSON output file path')
    args = parser.parse_args()

    rows = []
    baseEnv = os.environ.copy()
    baseEnv['PYTHONPATH'] = str(ROOT / 'src') + os.pathsep + str(ROOT)

    for docName in args.docName:
        chunkPath = ROOT / 'chunks' / f'{docName}.json'
        if not chunkPath.exists():
            raise FileNotFoundError(f'Missing chunk file: {chunkPath}')

        for strategy in args.strategies:
            env = baseEnv.copy()
            env['NER_STRATEGY'] = strategy
            env['GLINER_MODEL'] = os.getenv('GLINER_MODEL', 'NAMAA-Space/gliner_arabic-v2.1')
            env['GLINER_THRESHOLD'] = os.getenv('GLINER_THRESHOLD', '0.5')
            env['OLLAMA_URL'] = os.getenv('OLLAMA_URL', 'http://localhost:11434/v1/chat/completions')
            env['OLLAMA_TEXT_MODEL'] = os.getenv('OLLAMA_TEXT_MODEL', 'qwen2.5:72b-instruct-q4_K_M')
            env['OLLAMA_NUM_PARALLEL'] = os.getenv('OLLAMA_NUM_PARALLEL', '4')
            result = runStrategy(strategy, docName, env)
            rows.append(result)

    printTable(rows)

    if args.output:
        Path(args.output).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'Wrote benchmark results to {args.output}')


if __name__ == '__main__':
    main()