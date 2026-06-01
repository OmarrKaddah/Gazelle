import json
import pickle
import random
from pathlib import Path
import sklearn_crfsuite
from seqeval.metrics import classification_report


def loadTraining():
    raw = json.loads(Path('training/train_data.json').read_text(encoding='utf-8'))
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
    crf = sklearn_crfsuite.CRF(
        algorithm='lbfgs',
        c1=0.1,
        c2=0.1,
        max_iterations=200,
        all_possible_transitions=True,
    )
    crf.fit(X_train, y_train)
    return crf


def evaluate(crf, X_test, y_test):
    y_pred = crf.predict(X_test)
    print(classification_report(y_test, y_pred, digits=4))


def saveModel(crf):
    Path('models').mkdir(exist_ok=True)
    Path('models/crf.pkl').write_bytes(pickle.dumps(crf))
    print("Saved -> models/crf.pkl")


if __name__ == '__main__':
    X, y = loadTraining()
    print(f"Loaded {len(X)} sequences, {sum(len(s) for s in X)} tokens")
    X_train, y_train, X_test, y_test = splitData(X, y)
    print(f"Train: {len(X_train)} | Test: {len(X_test)} sequences")
    crf = trainCrf(X_train, y_train)
    evaluate(crf, X_test, y_test)
    saveModel(crf)
