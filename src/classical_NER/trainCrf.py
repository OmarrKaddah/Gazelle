import json
import pickle
import random
import sys
from pathlib import Path
import sklearn_crfsuite
from seqeval.metrics import classification_report


def loadTraining():
    base = Path(__file__).resolve().parent
    path = base / 'training' / 'train_data.json'
    print(f"[loadTraining] reading {path}")
    raw = json.loads(path.read_text(encoding='utf-8'))
    X = [[pair[0] for pair in seq] for seq in raw]
    y = [[pair[1] for pair in seq] for seq in raw]
    return X, y


def splitData(X, y, test_ratio=0.2, seed=42):
    combined = list(zip(X, y))
    random.seed(seed)
    random.shuffle(combined)
    cut = int(len(combined) * (1 - test_ratio))
    train, test = combined[:cut], combined[cut:]
    X_train, y_train = zip(*train)
    X_test,  y_test  = zip(*test)
    return list(X_train), list(y_train), list(X_test), list(y_test)


def trainCrf(X_train, y_train):
    print("[trainCrf] fitting CRF (lbfgs, c1=0.1, c2=0.1, max_iter=200)...")
    crf = sklearn_crfsuite.CRF(
        algorithm='lbfgs',
        c1=0.05,
        c2=0.05,
        max_iterations=500,
        all_possible_transitions=True,
        verbose=True,
    )
    crf.fit(X_train, y_train)
    print(f"[trainCrf] done — {len(crf.classes_)} classes: {crf.classes_}")
    return crf


def evaluate(crf, X_test, y_test):
    print("[evaluate] running predictions on test set...")
    y_pred = crf.predict(X_test)
    correct = sum(
        1 for seq_true, seq_pred in zip(y_test, y_pred)
        for t, p in zip(seq_true, seq_pred) if t == p
    )
    total = sum(len(s) for s in y_test)
    print(f"[evaluate] token accuracy: {correct}/{total} = {correct/total:.4f}")
    print("[evaluate] span-level F1 report:")
    print(classification_report(y_test, y_pred, digits=4))


def saveModel(crf, name='crf'):
    base = Path(__file__).resolve().parent
    model_dir = base / 'models'
    model_dir.mkdir(exist_ok=True)
    model_path = model_dir / f'{name}.pkl'
    model_path.write_bytes(pickle.dumps(crf))
    print(f"[saveModel] saved -> {model_path}")


if __name__ == '__main__':
    use_all   = '--all' in sys.argv
    nameArgs  = [a for a in sys.argv if a.startswith('--name=')]
    modelName = nameArgs[0].split('=', 1)[1] if nameArgs else 'crf'

    print("=" * 50)
    print("STEP 1 — load training data")
    X, y = loadTraining()
    total_tokens = sum(len(s) for s in X)
    print(f"  {len(X)} sequences, {total_tokens} tokens")

    if use_all:
        print("=" * 50)
        print("STEP 2 — using ALL data for training (official test set will be used for eval)")
        X_train, y_train = X, y
        print(f"  train: {len(X_train)} sequences ({sum(len(s) for s in X_train)} tokens)")
    else:
        print("=" * 50)
        print("STEP 2 — split train/test (80/20)")
        X_train, y_train, X_test, y_test = splitData(X, y)
        print(f"  train: {len(X_train)} sequences ({sum(len(s) for s in X_train)} tokens)")
        print(f"  test:  {len(X_test)} sequences ({sum(len(s) for s in X_test)} tokens)")

    print("=" * 50)
    print("STEP 3 — train")
    crf = trainCrf(X_train, y_train)

    if not use_all:
        print("=" * 50)
        print("STEP 4 — evaluate on internal test set")
        evaluate(crf, X_test, y_test)

    print("=" * 50)
    print("STEP 4 — save model" if use_all else "STEP 5 — save model")
    saveModel(crf, modelName)
    print("=" * 50)
    print("trainCrf done")
