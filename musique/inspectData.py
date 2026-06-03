import json
import random
from pathlib import Path

DEV = Path(__file__).resolve().parent / 'data' / 'musique_ans_v1.0_dev.jsonl'


def main():
    examples = [json.loads(l) for l in DEV.read_text(encoding='utf-8').splitlines() if l.strip()]
    print(f'{len(examples)} examples in {DEV.name}')
    random.seed(42)
    print(json.dumps(random.choice(examples), indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
