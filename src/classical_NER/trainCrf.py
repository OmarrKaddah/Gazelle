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
    print(f"reading {path}")
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
    # lbfgs with light L1/L2 — worked better than AP on this domain
    crf = sklearn_crfsuite.CRF(
        algorithm='lbfgs',
        c1=0.005,
        c2=0.005,
        max_iterations=3000,
        epsilon=1e-7,
        delta=1e-7,
        num_memories=15,
        all_possible_transitions=True,
        verbose=True,
    )
    crf.fit(X_train, y_train)
    print(f"done — {len(crf.classes_)} classes: {crf.classes_}")
    return crf


def evaluate(crf, X_test, y_test):
    print("running predictions on test set...")
    y_pred = crf.predict(X_test)

    correct = sum(
        1 for seq_true, seq_pred in zip(y_test, y_pred)
        for t, p in zip(seq_true, seq_pred) if t == p
    )
    total = sum(len(s) for s in y_test)
    print(f"token accuracy: {correct}/{total} = {correct/total:.4f}")
    print(classification_report(y_test, y_pred, digits=4))


def saveModel(crf, name='crf'):
    base = Path(__file__).resolve().parent
    model_dir = base / 'models'
    model_dir.mkdir(exist_ok=True)
    model_path = model_dir / f'{name}.pkl'
    model_path.write_bytes(pickle.dumps(crf))
    print(f"saved -> {model_path}")


if __name__ == '__main__':
    use_all   = '--all' in sys.argv
    nameArgs  = [a for a in sys.argv if a.startswith('--name=')]
    modelName = nameArgs[0].split('=', 1)[1] if nameArgs else 'crf'

    X, y = loadTraining()
    total_tokens = sum(len(s) for s in X)
    print(f"{len(X)} sequences, {total_tokens} tokens")

    if use_all:
        print("using all data for training (no internal split)")
        X_train, y_train = X, y
        print(f"  train: {len(X_train)} sequences ({sum(len(s) for s in X_train)} tokens)")
    else:
        print("splitting 80/20 train/test")
        X_train, y_train, X_test, y_test = splitData(X, y)
        print(f"  train: {len(X_train)} sequences ({sum(len(s) for s in X_train)} tokens)")
        print(f"  test:  {len(X_test)} sequences ({sum(len(s) for s in X_test)} tokens)")

    print("fitting CRF...")
    crf = trainCrf(X_train, y_train)

    if not use_all:
        evaluate(crf, X_test, y_test)

    saveModel(crf, modelName)
    print("trainCrf done")
