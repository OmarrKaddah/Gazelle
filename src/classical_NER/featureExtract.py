import json
import re
from pathlib import Path
from camel_tools.disambig.mle import MLEDisambiguator
from camel_tools.tagger.default import DefaultTagger

BASE_DIR = Path(__file__).resolve().parent

print("[featureExtract] loading CAMeL POS tagger...")
_tagger = DefaultTagger(MLEDisambiguator.pretrained('calima-msa-r13'), 'pos')
print("[featureExtract] tagger ready")


def loadAnnotations():
    path = BASE_DIR / 'annotations' / 'corrected.json'
    print(f"[loadAnnotations] reading {path}")
    raw = json.loads(path.read_text(encoding='utf-8'))
    out = []
    for task in raw:
        text = task['data']['text']
        source = task.get('annotations') or task.get('predictions') or [{}]
        result = source[0].get('result', [])
        spans = [
            {
                'start': ann['value']['start'],
                'end':   ann['value']['end'],
                'type':  ann['value']['labels'][0],
            }
            for ann in result
            if ann.get('type') == 'labels'
        ]
        out.append({'text': text, 'spans': spans, 'meta': task.get('meta', {})})
    total_spans = sum(len(a['spans']) for a in out)
    print(f"[loadAnnotations] {len(out)} tasks, {total_spans} labeled spans")
    return out


# TODO: This is a basic gazetteer loader — expand trigger sets after reviewing bank documents
def loadGazetteer():
    path = BASE_DIR / 'gazetteer' / 'gazetteer.json'
    print(f"[loadGazetteer] reading {path}")
    raw = json.loads(path.read_text(encoding='utf-8'))
    gazSets = {etype: set(forms) for etype, forms in raw.items()}
    for etype, s in gazSets.items():
        print(f"  {etype}: {len(s)} entries")
    orgTriggers   = {'بنك', 'شركة', 'هيئة', 'وزارة', 'مؤسسة', 'صندوق', 'اتحاد', 'لجنة', 'إدارة', 'مجلس'}
    moneyTriggers = {'جنيه', 'دولار', 'يورو', 'مليار', 'مليون', 'ألف', 'جنيهاً', 'دولاراً'}
    monthNames    = {'يناير', 'فبراير', 'مارس', 'إبريل', 'أبريل', 'مايو', 'يونيو',
                     'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'}
    print(f"[loadGazetteer] {len(orgTriggers)} org triggers, {len(moneyTriggers)} money triggers, {len(monthNames)} month names")
    return gazSets, orgTriggers, moneyTriggers, monthNames


def tokenize(text):
    pattern = r'[\d٠-٩]+-[\d٠-٩]+(?:-[\d٠-٩]+)*|[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿a-zA-Z0-9]+|[^\s]'
    return [
        {'word': m.group(), 'start': m.start(), 'end': m.end()}
        for m in re.finditer(pattern, text)
    ]


def posTag(words):
    return _tagger.tag(words)


def bioAlign(tokens, spans):
    labels = ['O'] * len(tokens)
    for span in spans:
        first = True
        for i, tok in enumerate(tokens):
            if tok['start'] >= span['start'] and tok['end'] <= span['end']:
                labels[i] = ('B-' if first else 'I-') + span['type']
                first = False
    return labels


def normalizeForLookup(word):
    word = re.sub(r'[ؐ-ًؚ-ٟ]', '', word)
    word = re.sub(r'[أإآ]', 'ا', word)
    return re.sub(r'ى', 'ي', word)


def morphFeatures(word):
    prep_prefixes = ('بال', 'لل', 'كال', 'وال', 'فال', 'بِال')
    prep_clitics  = ('بِ', 'لِ', 'كَ', 'وَ', 'ب', 'ل', 'ك', 'و', 'ف')

    has_prep = any(word.startswith(p) for p in prep_prefixes + prep_clitics)

    stem = word
    for prefix in prep_prefixes:
        if word.startswith(prefix):
            stem = word[len(prefix):]
            break
    else:
        for clitic in prep_clitics:
            if word.startswith(clitic) and len(word) > len(clitic) + 1:
                stem = word[len(clitic):]
                break

    has_def = stem.startswith('ال')
    if has_def:
        stem = stem[2:]

    return {'has_def_art': has_def, 'has_prep_clitic': has_prep, 'stem': stem}


def scriptFeatures(word):
    arabic_digits  = set('٠١٢٣٤٥٦٧٨٩')
    western_digits = set('0123456789')
    clause_pattern = re.compile(r'^[\d٠-٩]+-[\d٠-٩]+(-[\d٠-٩]+)*$')
    abbrev_pattern = re.compile(r'^[A-Z]{2,6}$')

    return {
        'is_arabic_num':   bool(word) and all(c in arabic_digits  for c in word),
        'is_western_num':  bool(word) and all(c in western_digits for c in word),
        'contains_latin':  bool(re.search(r'[a-zA-Z]', word)),
        'is_clause_ref':   bool(clause_pattern.match(word)),
        'is_abbreviation': bool(abbrev_pattern.match(word)),
    }


def charNgrams(word):
    feats = {}
    for i in range(len(word) - 1):
        feats[f'c2_{word[i:i+2]}'] = True
    for i in range(len(word) - 2):
        feats[f'c3_{word[i:i+3]}'] = True
    return feats


def contextTriggerFeatures(word, orgTriggers, moneyTriggers, monthNames):
    return {
        'is_org_trigger':   word in orgTriggers,
        'in_money_trigger': word in moneyTriggers,
        'in_month':         word in monthNames,
    }


def tokenFeatures(tokens, pos, i, orgTriggers, moneyTriggers, monthNames):
    word = tokens[i]['word']
    n    = len(tokens)

    def safeWord(j):
        if j < 0: return '__START__'
        if j >= n: return '__END__'
        return tokens[j]['word']

    def safePos(j):
        if j < 0: return '__START__'
        if j >= n: return '__END__'
        return pos[j] if pos[j] is not None else 'UNK'

    feats = {
        'word':     word,
        'pos':      pos[i] if pos[i] is not None else 'UNK',
        'is_first': i == 0,
        'prev_is_org_trigger': safeWord(i - 1) in orgTriggers,
        'w-1': safeWord(i - 1),
        'w+1': safeWord(i + 1),
        'p-2': safePos(i - 2),
        'p-1': safePos(i - 1),
        'p+1': safePos(i + 1),
        'p+2': safePos(i + 2),
    }

    feats.update(morphFeatures(word))
    feats.update(scriptFeatures(word))
    feats.update(charNgrams(word))
    feats.update(contextTriggerFeatures(word, orgTriggers, moneyTriggers, monthNames))
    return feats


def extractChunk(text, spans, orgTriggers, moneyTriggers, monthNames):
    tokens = tokenize(text)
    words  = [t['word'] for t in tokens]
    pos    = posTag(words)
    labels = bioAlign(tokens, spans)
    return [
        (tokenFeatures(tokens, pos, i, orgTriggers, moneyTriggers, monthNames), labels[i])
        for i in range(len(tokens))
    ]


def dumpTraining(sequences):
    (BASE_DIR / 'training').mkdir(exist_ok=True)
    out = [
        [[feats, label] for feats, label in seq]
        for seq in sequences
    ]
    (BASE_DIR / 'training' / 'train_data.json').write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print(f"[dumpTraining] saved {len(sequences)} sequences -> training/train_data.json")


if __name__ == '__main__':
    print("=" * 50)
    print("STEP 1 — load gazetteer")
    _, orgTriggers, moneyTriggers, monthNames = loadGazetteer()

    print("=" * 50)
    print("STEP 2 — load annotations")
    annotations = loadAnnotations()

    print("=" * 50)
    print("STEP 3 — extract features")
    sequences = []
    for i, a in enumerate(annotations):
        seq = extractChunk(a['text'], a['spans'], orgTriggers, moneyTriggers, monthNames)
        sequences.append(seq)
        entity_tokens = sum(1 for _, label in seq if label != 'O')
        print(f"  chunk {i+1}/{len(annotations)} | {len(seq)} tokens | {entity_tokens} entity tokens | doc: {a['meta'].get('docName', '?')}")

    print("=" * 50)
    print("STEP 4 — dump training data")
    dumpTraining(sequences)
    total_tokens = sum(len(s) for s in sequences)
    label_counts = {}
    for seq in sequences:
        for _, label in seq:
            label_counts[label] = label_counts.get(label, 0) + 1
    print(f"Total tokens: {total_tokens} across {len(sequences)} chunks")
    print("Label distribution:")
    for label, count in sorted(label_counts.items()):
        print(f"  {label}: {count}")
    print("=" * 50)
    print("featureExtract done")
