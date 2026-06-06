import _bootstrap  # noqa: F401
import os
import json
import threading
import numpy as np
import joblib
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, f1_score
from concurrent.futures import ThreadPoolExecutor
from routerFeatures import cueFeatures
from embedding import embedNanSafe



DATA_DIR = 'router/data'
EMB_CACHE = 'router/data/emb_cache.pkl'
ARTIFACT = 'src/models/router.joblib'
GLOBAL_PRECISION_TARGET = 0.85
SEED = 13


def loadRows(split):
    path = f'{DATA_DIR}/{split}.jsonl'
    rows = [json.loads(l) for l in open(path, encoding='utf-8')]
    return [r for r in rows if r.get('source') != 'example']


def labels(rows):
    return np.array([1 if r['label'] == 'global' else 0 for r in rows])


def cueMatrix(texts):
    return np.array([cueFeatures(t) for t in texts], dtype=np.float32)


def embedTextsCached(texts, name):
    cache = joblib.load(EMB_CACHE) if os.path.exists(EMB_CACHE) else {}
    missing = sorted(set(texts) - set(cache))
    if missing:
        total = len(missing)
        done = {'n': 0}
        lock = threading.Lock()

        def embedOne(text):
            v = np.asarray(embedNanSafe(text), dtype=np.float32)
            with lock:
                done['n'] += 1
                if done['n'] % 100 == 0 or done['n'] == total:
                    print(f'  embedded {done["n"]}/{total} new', flush=True)
            return text, v

        print(f'  embedding {total} new texts for {name}...', flush=True)
        with ThreadPoolExecutor(max_workers=8) as pool:
            for text, v in pool.map(embedOne, missing):
                cache[text] = v
        joblib.dump(cache, EMB_CACHE)
    else:
        print(f'  all {name} embeddings cached', flush=True)
    return np.array([cache[t] for t in texts], dtype=np.float32)


def tuneThreshold(probs, y):
    best = 0.5
    for t in np.linspace(0.1, 0.9, 81):
        pred = (probs >= t).astype(int)
        tp = int(((pred == 1) & (y == 1)).sum())
        fp = int(((pred == 1) & (y == 0)).sum())
        if tp + fp == 0:
            continue
        precision = tp / (tp + fp)
        if precision >= GLOBAL_PRECISION_TARGET and tp > 0:
            best = float(t)
            break
    return best


def report(name, yTrue, yPred):
    rep = classification_report(yTrue, yPred, target_names=['local', 'global'], digits=3)
    macro = f1_score(yTrue, yPred, average='macro')
    print(f'\n=== {name} | macro-F1 {macro:.3f} ===')
    print(rep)


def main():
    trainRows, testRows = loadRows('train'), loadRows('test')
    trainTexts = [r['text'] for r in trainRows]
    testTexts = [r['text'] for r in testRows]
    yTrain, yTest = labels(trainRows), labels(testRows)

    print('embedding train/test (cached)...', flush=True)
    embTrain = embedTextsCached(trainTexts, 'train')
    embTest = embedTextsCached(testTexts, 'test')
    cueTrain, cueTest = cueMatrix(trainTexts), cueMatrix(testTexts)

    # hand-crafted cues
    cueLR = Pipeline([('scale', StandardScaler()),
                      ('lr', LogisticRegression(max_iter=1000, class_weight='balanced'))])
    cueLR.fit(cueTrain, yTrain)
    report('cue + LR', yTest, cueLR.predict(cueTest))

    # char n-gram tfidf
    charLR = Pipeline([('tfidf', TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5), min_df=2)),
                       ('lr', LogisticRegression(max_iter=1000, class_weight='balanced'))])
    charLR.fit(trainTexts, yTrain)
    report('char(3-5) tfidf + LR', yTest, charLR.predict(testTexts))

    #  embedding + cues concatenated 1024 +14?
    embCueTrain = np.hstack([embTrain, StandardScaler().fit_transform(cueTrain)])
    embCueTest = np.hstack([embTest, StandardScaler().fit(cueTrain).transform(cueTest)])
    embCueLR = LogisticRegression(max_iter=1000, class_weight='balanced').fit(embCueTrain, yTrain)
    report('embedding + cues + LR', yTest, embCueLR.predict(embCueTest))

   
    base = Pipeline([('scale', StandardScaler()),
                     ('lr', LogisticRegression(max_iter=1000, class_weight='balanced'))])
    fitEmb, valEmb, fitY, valY = train_test_split(embTrain, yTrain, test_size=0.2,
                                                  stratify=yTrain, random_state=SEED)
    calVal = CalibratedClassifierCV(base, method='sigmoid', cv=5).fit(fitEmb, fitY)
    threshold = tuneThreshold(calVal.predict_proba(valEmb)[:, 1], valY)

    deployed = CalibratedClassifierCV(base, method='sigmoid', cv=5).fit(embTrain, yTrain)
    probsTest = deployed.predict_proba(embTest)[:, 1]
    report(f'embedding + calibrated LR (T={threshold:.3f}, DEPLOYED)',
           yTest, (probsTest >= threshold).astype(int))

    os.makedirs('src/models', exist_ok=True)
    joblib.dump({'model': deployed, 'threshold': threshold, 'globalIdx': 1,
                 'featureVersion': 1}, ARTIFACT)
    print(f'\nsaved deployed model -> {ARTIFACT}')


if __name__ == '__main__':
    main()
