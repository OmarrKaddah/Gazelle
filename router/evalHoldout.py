import _bootstrap  # noqa: F401
import json
import numpy as np
import joblib
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, f1_score
from train import loadRows, labels, cueMatrix, embedTextsCached, tuneThreshold
from routerFeatures import cueFeatures



HOLDOUT = 'router/data/holdout_llm.jsonl'
ARTIFACT = 'src/models/router.joblib'


def loadHoldout(agreeOnly):
    rows = [json.loads(l) for l in open(HOLDOUT, encoding='utf-8')]
    return [r for r in rows if r['agree']] if agreeOnly else rows


def evalSlice(name, yTrue, yPred):
    macro = f1_score(yTrue, yPred, average='macro', zero_division=0)
    rep = classification_report(yTrue, yPred, target_names=['local', 'global'],
                                digits=3, zero_division=0)
    print(f'\n=== {name} | n={len(yTrue)} | macro-F1 {macro:.3f} ===')
    print(rep)
    return macro


def byLang(name, rows, yTrue, yPred):
    yTrue, yPred = np.array(yTrue), np.array(yPred)
    langs = np.array([r['lang'] for r in rows])
    print(f'\n######## {name} ########')
    evalSlice(f'{name} | ALL', yTrue, yPred)
    for lg in ('ar', 'en'):
        m = langs == lg
        evalSlice(f'{name} | {lg.upper()}', yTrue[m], yPred[m])


def main():
    rows = loadHoldout(agreeOnly=False)
    texts = [r['text'] for r in rows]
    yTrue = np.array([1 if r['label'] == 'global' else 0 for r in rows])

    # train the baselines on the synthetic train set, test on the real holdout
    trainRows = loadRows('train')
    trainTexts = [r['text'] for r in trainRows]
    yTrain = labels(trainRows)

    print('embedding holdout (Ollama bge-m3, cached)...', flush=True)
    embHold = embedTextsCached(texts, 'holdout')
    embTrain = embedTextsCached(trainTexts, 'train')

    # cue-LR
    cueLR = Pipeline([('scale', StandardScaler()),
                      ('lr', LogisticRegression(max_iter=1000, class_weight='balanced'))])
    cueLR.fit(cueMatrix(trainTexts), yTrain)
    byLang('cue + LR', rows, yTrue, cueLR.predict(cueMatrix(texts)))

    # char-TFIDF-LR — expected to collapse on Arabic (disjoint script vs EN-heavy train)
    charLR = Pipeline([('tfidf', TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5), min_df=2)),
                       ('lr', LogisticRegression(max_iter=1000, class_weight='balanced'))])
    charLR.fit(trainTexts, yTrain)
    byLang('char(3-5) tfidf + LR', rows, yTrue, charLR.predict(texts))

    # deployed embedding-LR 
    art = joblib.load(ARTIFACT)
    model, storedT = art['model'], art['threshold']
    probs = model.predict_proba(embHold)[:, 1]
    byLang(f'embedding-LR (stored T={storedT:.3f})', rows, yTrue, (probs >= storedT).astype(int))

   
    newT = tuneThreshold(probs, yTrue)
    byLang(f'embedding-LR (retuned T={newT:.3f})', rows, yTrue, (probs >= newT).astype(int))
    print(f'\n>>> stored threshold {storedT:.3f} -> retuned on real holdout {newT:.3f}')


if __name__ == '__main__':
    main()
