import _bootstrap  # noqa: F401
import sys
import subprocess
from pathlib import Path

CLASSICAL_NER = Path(__file__).resolve().parent.parent / 'src' / 'classical_NER'
PYTHON = sys.executable


def run(label, cmd):
    print(f"\n{'='*55}")
    print(f"  {label}")
    print(f"{'='*55}")
    subprocess.run([PYTHON] + cmd, check=True)


if __name__ == '__main__':
    import argparse

    ap = argparse.ArgumentParser(
        description='Run the full classical NER pipeline.',
        epilog="""
examples:
  python runners/runNerPipeline.py
  python runners/runNerPipeline.py --wikiann --anercorp --name=crf_combined
  python runners/runNerPipeline.py --wikiann --anercorp --name=crf_combined --all
        """
    )
    ap.add_argument('--wikiann',  action='store_true', help='Include WikiANN base in training')
    ap.add_argument('--anercorp', action='store_true', help='Include ANERcorp base in training')
    ap.add_argument('--name',     default='crf_combined', help='Model name  (default: crf_combined)')
    ap.add_argument('--all',      action='store_true',    help='Train on full data, no internal test split')
    ap.add_argument('--docs',     default=None,           help='Comma-separated doc names for inference (default: all bank docs)')
    args = ap.parse_args()

    sources = ['bank']
    if args.wikiann:  sources.append('wikiann')
    if args.anercorp: sources.append('anercorp')

    print(f"\nNER pipeline  |  data: {' + '.join(sources)}  |  model: {args.name}\n")

    # 1 — gazetteer
    run('Step 1 — build gazetteer', [str(CLASSICAL_NER / 'buildGazetteer.py')])

    # 2 — convert GLiNER extractions to annotations
    bank_docs = sorted(
        p.stem for p in Path('chunks').glob('*.json')
        if not p.stem.startswith('wikiann') and not p.stem.startswith('anercorp')
    )
    run(f'Step 2 — convert GLiNER extractions ({len(bank_docs)} docs)',
        [str(CLASSICAL_NER / 'extractionsToCorrections.py')] + bank_docs)

    # 3 — feature extraction
    feat_cmd = [str(CLASSICAL_NER / 'featureExtract.py')]
    if args.wikiann:  feat_cmd.append('--wikiann')
    if args.anercorp: feat_cmd.append('--anercorp')
    run('Step 3 — feature extraction', feat_cmd)

    # 4 — train
    train_cmd = [str(CLASSICAL_NER / 'trainCrf.py'), f'--name={args.name}']
    if args.all: train_cmd.append('--all')
    run(f'Step 4 — train CRF ({args.name})', train_cmd)

    # 5 — inference
    infer_cmd = [str(CLASSICAL_NER / 'runCrf.py'), f'--model={args.name}']
    if args.docs: infer_cmd.append(f'--docs={args.docs}')
    run(f'Step 5 — run inference', infer_cmd)

    print(f"\n{'='*55}")
    print(f"  Done")
    print(f"  Entities  →  extractions/{args.name}/")
    print(f"  Model     →  src/classical_NER/models/{args.name}.pkl")
    print(f"{'='*55}")
    print(f"\nTo evaluate:")
    print(f"  python src/classical_NER/evalNer.py wikiann_test --model={args.name}")
    print(f"  python src/classical_NER/evalNer.py anercorp_test --model={args.name}")