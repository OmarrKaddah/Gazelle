import _bootstrap

import json
import os
import random
import re
import hashlib
import collections
import glob

random.seed(13)

TARGET_PER_CELL = 500
NOISE_RATE = 0.15
DEDUP_JACCARD = 0.85

# ---------------------------------------------------------------------------
# Calendar word sets for isGoodSlot
# ---------------------------------------------------------------------------
EN_CALENDAR = {
    'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
    'january', 'february', 'march', 'april', 'may', 'june',
    'july', 'august', 'september', 'october', 'november', 'december',
    'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
    'today', 'tomorrow', 'yesterday', 'week', 'month', 'year', 'day',
}

AR_CALENDAR = {
    'السبت', 'الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة',
    'يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو',
    'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر',
    'اليوم', 'أمس', 'غدا', 'الشهر', 'العام', 'السنة', 'الأسبوع',
}

# ASCII + Arabic-Indic digit pattern
_DIGIT_RE = re.compile(r'[0-9٠١٢٣٤٥٦٧٨٩]')

# Arabic harakat / diacritics (U+064B–U+065F and U+0670)
_HARAKAT_RE = re.compile(r'[ً-ٰٟ]')


def stripHarakat(text):
    return _HARAKAT_RE.sub('', text)


def isGoodSlot(term, lang):
    """Return True iff term is a clean, domain-relevant slot value."""
    if _DIGIT_RE.search(term):
        return False
    tokens = term.split()
    if len(tokens) < 2:
        return False
    if len(term) < 6:
        return False
    tokens_lower = [t.lower() for t in tokens]
    if lang == 'en':
        calendar_set = EN_CALENDAR
        stops = EN_STOPS
        if set(tokens_lower) <= stops:
            return False
        if any(t in calendar_set for t in tokens_lower):
            return False
    else:
        calendar_set = AR_CALENDAR
        if any(t in calendar_set for t in tokens):
            return False
        # Reject if first or last token is <= 2 chars (dangling clitics / truncated fragments)
        if len(tokens[0]) <= 2 or len(tokens[-1]) <= 2:
            return False
    return True



AR_STOPS = {
    'في', 'من', 'إلى', 'على', 'عن', 'مع', 'هذا', 'هذه', 'التي', 'الذي',
    'أن', 'إن', 'كان', 'قد', 'ما', 'لا', 'و', 'أو', 'ثم', 'كل', 'بعد',
    'قبل', 'عند', 'حتى', 'الى', 'علي', 'ان', 'وان', 'كما', 'لم', 'لن',
    'هو', 'هي', 'هم', 'نحن', 'انت', 'أنت', 'لي', 'له', 'لها', 'لهم',
    'ذلك', 'تلك', 'هناك', 'أيضا', 'أيضاً', 'إذا', 'فإن', 'فان', 'بما',
    'عدد', 'يتم', 'يكون', 'كانت', 'وقد', 'كذلك', 'حيث', 'إذ', 'أي',
    'ولا', 'ومن', 'وفي', 'وعلى', 'وإلى', 'والتي', 'والذي', 'ببعض',
    'عليه', 'عليها', 'عليهم', 'منه', 'منها', 'منهم', 'وهو', 'وهي',
    'بين', 'خلال', 'ذات', 'غير', 'دون', 'حول', 'ضد', 'نحو', 'وفق',
    'إلا', 'الا', 'بل', 'لكن', 'أما', 'اما', 'مما', 'بها', 'بهم',
    'فيه', 'فيها', 'فيهم', 'عنه', 'عنها', 'عنهم', 'يجب', 'يمكن',
    'للبنوك', 'البنوك', 'البنك',
    'التحويلات', 'المالية،', 'المالية',
}


AR_CLEAN_RE = re.compile(r'^[؀-ۿ٠-٩\s،؛\-]+$')

EN_STOPS = {
    'the', 'a', 'an', 'of', 'in', 'to', 'and', 'or', 'for', 'with',
    'by', 'on', 'at', 'from', 'as', 'is', 'are', 'was', 'were', 'be',
    'been', 'it', 'its', 'this', 'that', 'these', 'those', 'which',
    'who', 'what', 'how', 'when', 'where', 'not', 'no', 'nor', 'but',
    'so', 'yet', 'both', 'each', 'all', 'any', 'more', 'most', 'such',
    'than', 'then', 'also', 'into', 'over', 'after', 'before', 'during',
    'between', 'through', 'within', 'under', 'above', 'about', 'per',
    'has', 'have', 'had', 'will', 'would', 'should', 'could', 'may',
    'their', 'they', 'them', 'we', 'our', 'he', 'she', 'his', 'her',
    'can', 'do', 'does', 'did', 'if', 'while', 'since', 'however',
}


EN_LOCAL_TEMPLATES = [
    ("What is {e}?", "en_local_01"),
    ("Who is {e}?", "en_local_02"),
    ("When was {e} established?", "en_local_03"),
    ("Define {e}.", "en_local_04"),
    ("What is the definition of {e}?", "en_local_05"),
    ("How much is {e}?", "en_local_06"),
    ("What is the value of {e}?", "en_local_07"),
    ("Where is {e} located?", "en_local_08"),
    ("What does {e} refer to?", "en_local_09"),
    ("What is the role of {e}?", "en_local_10"),
    ("What is the requirement for {e}?", "en_local_11"),
    ("Give details about {e}.", "en_local_12"),
]

EN_GLOBAL_TEMPLATES = [
    ("What are the main themes related to {t} across the documents?", "en_global_01"),
    ("What overall patterns emerge regarding {t} in the corpus?", "en_global_02"),
    ("How is {t} discussed across the documents?", "en_global_03"),
    ("Summarize the key issues around {t} across the corpus.", "en_global_04"),
    ("What are the major trends concerning {t}?", "en_global_05"),
    ("Compare how different documents address {t}.", "en_global_06"),
    ("What are the recurring concerns about {t} throughout the corpus?", "en_global_07"),
    ("What is the overall narrative about {t} that emerges from the documents?", "en_global_08"),
    ("Across the documents, what are the most discussed aspects of {t}?", "en_global_09"),
    ("What broad conclusions can be drawn about {t} from the corpus as a whole?", "en_global_10"),
    ("What are the common themes linking {t} across articles?", "en_global_11"),
]

AR_LOCAL_TEMPLATES = [
    ("ما هو {e}؟", "ar_local_01"),
    ("ما هي {e}؟", "ar_local_02"),
    ("من هو {e}؟", "ar_local_03"),
    ("ما تعريف {e}؟", "ar_local_04"),
    ("ما المقصود بـ {e}؟", "ar_local_05"),
    ("متى تم إنشاء {e}؟", "ar_local_06"),
    ("كم تبلغ قيمة {e}؟", "ar_local_07"),
    ("ما هي قيمة {e}؟", "ar_local_08"),
    ("ما هو دور {e}؟", "ar_local_09"),
    ("ما هي متطلبات {e}؟", "ar_local_10"),
    ("ما هي الشروط الخاصة بـ {e}؟", "ar_local_11"),
    ("أعطِ تفاصيل حول {e}.", "ar_local_12"),
]

AR_GLOBAL_TEMPLATES = [
    ("ما هي الموضوعات الرئيسية المتعلقة بـ {t} عبر الوثائق؟", "ar_global_01"),
    ("ما هي الاتجاهات العامة فيما يخص {t} في المستندات؟", "ar_global_02"),
    ("كيف يتم تناول {t} عبر الوثائق المختلفة؟", "ar_global_03"),
    ("لخّص القضايا الرئيسية المتعلقة بـ {t} عبر المجموعة.", "ar_global_04"),
    ("ما هي الأنماط المتكررة بشأن {t} في الوثائق؟", "ar_global_05"),
    ("قارن كيفية معالجة الوثائق المختلفة لموضوع {t}.", "ar_global_06"),
    ("ما هي المخاوف المتكررة حول {t} في جميع المستندات؟", "ar_global_07"),
    ("ما هي الصورة العامة التي تظهر حول {t} من الوثائق ككل؟", "ar_global_08"),
    ("ما أبرز الجوانب التي تتم مناقشتها بخصوص {t} عبر المستندات؟", "ar_global_09"),
    ("ما الاستنتاجات العامة التي يمكن استخلاصها حول {t} من المجموعة بأكملها؟", "ar_global_10"),
]


TYPE_TMPL_EN = {
    'Person': 1,     
    'Date': 2,       
    'Number': 5,     
    'Percent': 6,    
    'Money': 5,
    'Location': 7,    
    'Org': 9,       
    'Organization': 9,
    'Event': 0,
    'default': 0,   
}

TYPE_TMPL_AR = {
    'Person': 2,     
    'Date': 5,       
    'Number': 6,     
    'Percent': 7,
    'Money': 7,
    'Location': 0,
    'Org': 8,
    'Organization': 8,
    'default': 0,
}



def isArabicScript(text):
    return bool(re.search(r'[؀-ۿ]', text))

def stripMarkdown(text):
    text = re.sub(r'#+\s*', '', text)
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'\|', ' ', text)
    text = re.sub(r'`[^`]*`', '', text)
    text = re.sub(r'\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'[-_]{2,}', ' ', text)
    return text

def tokenize(text):
    return re.findall(r'[؀-ۿ\w]+', text)

def ngrams(tokens, n):
    return [tuple(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]

def isCleanArTerm(term):
    return bool(AR_CLEAN_RE.match(term))

def mineTerms(mdPaths, stops, topN=40, arFilter=False):
    lang = 'ar' if arFilter else 'en'
    counts = collections.Counter()
    for path in mdPaths:
        with open(path, encoding='utf-8') as f:
            raw = f.read()
        text = stripMarkdown(raw)
        if arFilter:
            text = stripHarakat(text)
        tokens = tokenize(text)
        tokens_lower = [t.lower() for t in tokens]
        for n in (2, 3):
            for gram in ngrams(tokens_lower, n):
                if all(t not in stops for t in gram):
                    term = ' '.join(gram)
                    if arFilter and not isCleanArTerm(term):
                        continue
                    counts[term] += 1
    # Strip leading/trailing Arabic punctuation from mined terms
    cleaned = []
    for term, _ in counts.most_common(topN * 4):
        term = term.strip('،؛:؟!')
        if not term:
            continue
        if arFilter and not isCleanArTerm(term):
            continue
        if not isGoodSlot(term, lang):
            continue
        cleaned.append(term)
        if len(cleaned) >= topN:
            break
    return cleaned

def loadGraphEntities(path, arClean=False):
    lang = 'ar' if arClean else 'en'
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    entities = []
    for chunk in data:
        for ent in chunk.get('entities', []):
            if isinstance(ent, (list, tuple)) and len(ent) >= 2:
                name, etype = ent[0], ent[1]
                if not name:
                    continue
                if lang == 'en' and isArabicScript(name):
                    continue
                if arClean:
                    name = stripHarakat(name)
                    if isArabicScript(name) and not isCleanArTerm(name):
                        continue
                if not isGoodSlot(name, lang):
                    continue
                entities.append((name, etype))
    return entities

def topEntities(path, topN=40, arClean=False):
    ents = loadGraphEntities(path, arClean=arClean)
    counts = collections.Counter(name for name, _ in ents)
    top_names = {name for name, _ in counts.most_common(topN)}
    seen = set()
    result = []
    for name, etype in ents:
        if name in top_names and name not in seen:
            seen.add(name)
            result.append((name, etype))
    return result

def shingles4(text):
    t = text.lower().replace(' ', '')
    return {t[i:i+4] for i in range(len(t) - 3)}

def jaccard(a, b):
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / (len(a) + len(b) - inter)

def normalizeText(text):
    return re.sub(r'\s+', ' ', text.strip().lower())

def dedupRows(rows):
    by_label_lang = collections.defaultdict(list)
    for r in rows:
        by_label_lang[(r['label'], r['lang'])].append(r)

    kept = []
    dropped = 0
    for key, group in by_label_lang.items():
        seen_texts = set()
        kept_group = []
        kept_shingles = []
        for r in group:
            norm = normalizeText(r['text'])
            if norm in seen_texts:
                dropped += 1
                continue
            seen_texts.add(norm)
            sh = shingles4(norm)
            dup = False
            for ksh in kept_shingles:
                if jaccard(sh, ksh) > DEDUP_JACCARD:
                    dup = True
                    break
            if dup:
                dropped += 1
            else:
                kept_group.append(r)
                kept_shingles.append(sh)
        kept.extend(kept_group)
    return kept, dropped

def applyNoise(text, lang):
    r = random.random()
    if r < 0.05 and lang == 'en':
        text = text.lower()
    elif r < 0.10:
        text = re.sub(r'[?؟]$', '', text).rstrip()
    elif r < 0.15:
        text = text.rstrip('.')
    return text

def makeRow(text, label, lang, domain, source, template_id, doc):
    return {
        'text': text,
        'label': label,
        'lang': lang,
        'domain': domain,
        'source': source,
        'template_id': template_id,
        'doc': doc,
    }

def pickEnLocalTemplate(etype):
    idx = TYPE_TMPL_EN.get(etype, TYPE_TMPL_EN['default'])
    tmpl, tid = EN_LOCAL_TEMPLATES[idx]
    return tmpl, tid

def pickArLocalTemplate(etype):
    idx = TYPE_TMPL_AR.get(etype, TYPE_TMPL_AR['default'])
    tmpl, tid = AR_LOCAL_TEMPLATES[idx]
    return tmpl, tid

def generateTemplated(slots, templates, label, lang, domain, doc, source='template', cap=TARGET_PER_CELL):
    rows = []
    pairs = [(s, t) for s in slots for t in templates]
    random.shuffle(pairs)
    pairs = pairs[:cap]
    slot_key = '{e}' if label == 'local' else '{t}'
    for i, (slot_val, (tmpl, tid)) in enumerate(pairs):
        if isinstance(slot_val, tuple):
            name, etype = slot_val
            if lang == 'en':
                tmpl, tid = pickEnLocalTemplate(etype)
            else:
                tmpl, tid = pickArLocalTemplate(etype)
        else:
            name = slot_val
        text = tmpl.replace(slot_key, name)
        if source == 'template' and random.random() < NOISE_RATE:
            text = applyNoise(text, lang)
        rows.append(makeRow(text, label, lang, domain, source, tid, doc))
    return rows

# ---------------------------------------------------------------------------
# Load MuSiQue gold questions
# ---------------------------------------------------------------------------

def loadMusiqueGold(path, split):
    rows = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            q = obj.get('question', '').strip()
            if q:
                rows.append(makeRow(q, 'local', 'en', 'musique', 'gold', None, split))
    return rows

# ---------------------------------------------------------------------------
# Load 2wiki gold questions
# ---------------------------------------------------------------------------

def load2wikiGold(path, split):
    rows = []
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    for obj in data:
        q = obj.get('question', '').strip()
        if q:
            rows.append(makeRow(q, 'local', 'en', '2wiki', 'gold', None, split))
    return rows

# ---------------------------------------------------------------------------
# Load llm_news global questions
# ---------------------------------------------------------------------------

def loadLlmNews(path):
    rows = []
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    for obj in data:
        q = obj.get('text', '').strip()
        if q:
            rows.append(makeRow(q, 'global', 'en', 'news', 'llm_news', None, 'questions_slice'))
    return rows

# ---------------------------------------------------------------------------
# Doc_Out file classification
# ---------------------------------------------------------------------------

def classifyDocOut():
    doc_dir = 'Doc_Out'
    ar_paths, en_paths = [], []
    for path in glob.glob(os.path.join(doc_dir, '*.md')):
        fname = os.path.basename(path)
        if fname.endswith('_ar.md'):
            ar_paths.append(path)
        else:
            en_paths.append(path)
    return ar_paths, en_paths

# ---------------------------------------------------------------------------
# Doc split by doc name (85/15)
# ---------------------------------------------------------------------------

def splitDocs(doc_names):
    docs = sorted(set(doc_names))
    random.shuffle(docs)
    cut = max(1, int(len(docs) * 0.85))
    train_docs = set(docs[:cut])
    test_docs = set(docs[cut:])
    return train_docs, test_docs

def splitRows(rows, train_frac=0.85):
    """Split a list of rows directly when doc-level split yields nothing in test."""
    idxs = list(range(len(rows)))
    random.shuffle(idxs)
    cut = max(1, int(len(rows) * train_frac))
    train = [rows[i] for i in idxs[:cut]]
    test = [rows[i] for i in idxs[cut:]]
    return train, test

# ---------------------------------------------------------------------------
# Main generation
# ---------------------------------------------------------------------------

def splitByTemplate(rows, train_frac=0.85):
    """Hold whole templates out for test so the test set measures generalisation to
    UNSEEN phrasings, not memorised template skeletons. Rows without a template_id
    (gold/entity inversions) fall back to a row-index split."""
    withT = [r for r in rows if r.get('template_id')]
    withoutT = [r for r in rows if not r.get('template_id')]
    tmpls = sorted({r['template_id'] for r in withT})
    if len(tmpls) < 3:
        return splitRows(rows, train_frac)
    random.shuffle(tmpls)
    cut = max(1, int(len(tmpls) * train_frac))
    trainT = set(tmpls[:cut])
    tr = [r for r in withT if r['template_id'] in trainT]
    te = [r for r in withT if r['template_id'] not in trainT]
    if withoutT:
        ntr, nte = splitRows(withoutT, train_frac)
        tr, te = tr + ntr, te + nte
    return tr, te


def addSplit(rows_train, rows_test, rows):
    """Split rows 85/15 by template (templates disjoint across train/test)."""
    tr, te = splitByTemplate(rows)
    rows_train.extend(tr)
    rows_test.extend(te)


def main():
    rows_train = []
    rows_test = []

    # --- MuSiQue gold LOCAL (en) — natural train/dev split ---
    mq_train_all = loadMusiqueGold('musique/data/musique_ans_v1.0_train.jsonl', 'musique_train')
    mq_dev_all = loadMusiqueGold('musique/data/musique_ans_v1.0_dev.jsonl', 'musique_dev')
    random.shuffle(mq_train_all)
    random.shuffle(mq_dev_all)
    rows_train.extend(mq_train_all[:TARGET_PER_CELL])
    rows_test.extend(mq_dev_all[:TARGET_PER_CELL])

    # --- 2wiki gold LOCAL (en) — natural train/dev split ---
    wiki_train_all = load2wikiGold('twowiki/data/train.json', '2wiki_train')
    wiki_dev_all = load2wikiGold('twowiki/data/dev.json', '2wiki_dev')
    random.shuffle(wiki_train_all)
    random.shuffle(wiki_dev_all)
    rows_train.extend(wiki_train_all[:TARGET_PER_CELL])
    rows_test.extend(wiki_dev_all[:TARGET_PER_CELL])

    # --- llm_news global (en) — all go to train (only 10 rows) ---
    llm_news = loadLlmNews('sensemaking/questions_slice.json')
    rows_train.extend(llm_news)

    # --- apnews LOCAL templated (en) ---
    apnews_ents = topEntities('extractions/apnews_graph.json', topN=60)
    apnews_en_local_rows = generateTemplated(
        apnews_ents, EN_LOCAL_TEMPLATES, 'local', 'en', 'news', 'apnews_graph', cap=TARGET_PER_CELL
    )
    addSplit(rows_train, rows_test, apnews_en_local_rows)

    # --- apnews GLOBAL templated (en) ---
    apnews_counts = collections.Counter(
        name for name, _ in loadGraphEntities('extractions/apnews_graph.json', arClean=False)
    )
    apnews_global_slots = [name for name, _ in apnews_counts.most_common(40) if isGoodSlot(name, 'en')]
    apnews_en_global_rows = generateTemplated(
        apnews_global_slots, EN_GLOBAL_TEMPLATES, 'global', 'en', 'news', 'apnews_graph', cap=TARGET_PER_CELL
    )
    addSplit(rows_train, rows_test, apnews_en_global_rows)

    # --- 2wiki LOCAL templated (en) — for balance ---
    wiki_ents = topEntities('extractions/2wiki_graph.json', topN=60)
    wiki_local_rows = generateTemplated(
        wiki_ents, EN_LOCAL_TEMPLATES, 'local', 'en', '2wiki', '2wiki_graph', cap=TARGET_PER_CELL
    )
    addSplit(rows_train, rows_test, wiki_local_rows)

    # --- 2wiki GLOBAL templated (en) ---
    wiki_counts = collections.Counter(name for name, _ in loadGraphEntities('extractions/2wiki_graph.json', arClean=False))
    wiki_global_slots = [name for name, _ in wiki_counts.most_common(40) if isGoodSlot(name, 'en')]
    wiki_global_rows = generateTemplated(
        wiki_global_slots, EN_GLOBAL_TEMPLATES, 'global', 'en', '2wiki', '2wiki_graph', cap=TARGET_PER_CELL
    )
    addSplit(rows_train, rows_test, wiki_global_rows)

    # --- CBE English LOCAL + GLOBAL templated ---
    ar_paths, en_paths = classifyDocOut()

    cbe_en_terms = mineTerms(en_paths, EN_STOPS, topN=40)
    cbe_en_ents = []
    for p in ['extractions/1-ownfunds--discussionpaper_graph.json',
              'extractions/2-credit-risk--discussionpaper_graph.json',
              'extractions/4-operational-risk-discussionpaper_graph.json']:
        if os.path.exists(p):
            cbe_en_ents.extend(topEntities(p, topN=20))

    cbe_en_local_slots = cbe_en_ents if cbe_en_ents else [(t, 'default') for t in cbe_en_terms]
    cbe_en_local_rows = generateTemplated(
        cbe_en_local_slots, EN_LOCAL_TEMPLATES, 'local', 'en', 'cbe', 'cbe_en_docs', cap=TARGET_PER_CELL
    )
    cbe_en_global_rows = generateTemplated(
        cbe_en_terms, EN_GLOBAL_TEMPLATES, 'global', 'en', 'cbe', 'cbe_en_docs', cap=TARGET_PER_CELL
    )
    addSplit(rows_train, rows_test, cbe_en_local_rows)
    addSplit(rows_train, rows_test, cbe_en_global_rows)

    # --- CBE Arabic LOCAL + GLOBAL templated ---
    cbe_ar_terms = mineTerms(ar_paths, AR_STOPS, topN=80, arFilter=True)

    ar_graph_paths = [
        'extractions/12-april-2_131_ar_graph.json',
        'extractions/16-august_125_ar_graph.json',
    ]
    # Collect all unique AR entity names (not just top-N) for a larger local slot pool
    cbe_ar_ents = []
    seen_ar_ent_names = set()
    for p in ar_graph_paths:
        if os.path.exists(p):
            for name, etype in loadGraphEntities(p, arClean=True):
                if name not in seen_ar_ent_names:
                    seen_ar_ent_names.add(name)
                    cbe_ar_ents.append((name, etype))

    # Entity tuples: each gets its type-matched template (one row per entity)
    ar_ent_rows = []
    for name, etype in cbe_ar_ents:
        tmpl, tid = pickArLocalTemplate(etype)
        text = tmpl.replace('{e}', name)
        ar_ent_rows.append(makeRow(text, 'local', 'ar', 'cbe', 'cbe_ar_docs', tid, 'cbe_ar_docs'))
    # Term slots: full cross-product with all AR-local templates
    ar_term_slots = [t for t in cbe_ar_terms]
    ar_local_cap = int(TARGET_PER_CELL / 0.85) + 50
    cbe_ar_term_rows = generateTemplated(
        ar_term_slots, AR_LOCAL_TEMPLATES, 'local', 'ar', 'cbe', 'cbe_ar_docs', cap=ar_local_cap
    )
    cbe_ar_local_rows = ar_ent_rows + cbe_ar_term_rows
    cbe_ar_global_rows = generateTemplated(
        cbe_ar_terms, AR_GLOBAL_TEMPLATES, 'global', 'ar', 'cbe', 'cbe_ar_docs', cap=TARGET_PER_CELL
    )
    addSplit(rows_train, rows_test, cbe_ar_local_rows)
    addSplit(rows_train, rows_test, cbe_ar_global_rows)

    # --- Dedup ---
    rows_train, dropped_train = dedupRows(rows_train)
    rows_test, dropped_test = dedupRows(rows_test)
    dropped_total = dropped_train + dropped_test

    random.shuffle(rows_train)
    random.shuffle(rows_test)

    # --- Write outputs ---
    os.makedirs('router/data', exist_ok=True)

    with open('router/data/train.jsonl', 'w', encoding='utf-8') as f:
        for r in rows_train:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    with open('router/data/test.jsonl', 'w', encoding='utf-8') as f:
        for r in rows_test:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    holdout_comment = {
        "_comment": (
            "holdout_real.jsonl — hand-authored real queries for final evaluation. "
            "Write ~80-100 genuine bilingual questions (mix ar/en, mix local/global) "
            "that you or domain experts actually want the router to answer correctly. "
            "Do NOT use templates. source must be 'real'. "
            "Schema: {text, label, lang, domain, source, template_id, doc}. "
            "template_id=null for all real rows. "
            "See README.md for the full schema."
        )
    }
    example_rows = [
        makeRow("ما هي متطلبات كفاية رأس المال وفق اتفاقية بازل؟", "local", "ar", "cbe", "example", None, "example"),
        makeRow("ما هي الاتجاهات العامة فيما يخص الشمول المالي في المستندات؟", "global", "ar", "cbe", "example", None, "example"),
        makeRow("What is the minimum capital adequacy ratio required by CBE?", "local", "en", "cbe", "example", None, "example"),
        makeRow("What are the main themes related to financial inclusion across the documents?", "global", "en", "cbe", "example", None, "example"),
    ]
    with open('router/data/holdout_real.jsonl', 'w', encoding='utf-8') as f:
        f.write(json.dumps(holdout_comment, ensure_ascii=False) + '\n')
        for r in example_rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    # --- Summary table ---
    printSummary(rows_train, rows_test, dropped_total)
    spotCheck(rows_train)


def printSummary(rows_train, rows_test, dropped):
    def countTable(rows, split_name):
        counter = collections.Counter()
        for r in rows:
            key = (r['label'], r['lang'], r['domain'], r['source'])
            counter[key] += 1
        print(f'\n=== {split_name} ({len(rows)} rows) ===')
        print(f'{"label":<8} {"lang":<5} {"domain":<10} {"source":<12} {"count":>6}')
        print('-' * 50)
        for key in sorted(counter):
            label, lang, domain, source = key
            print(f'{label:<8} {lang:<5} {domain:<10} {source:<12} {counter[key]:>6}')
        local_n = sum(v for (l, *_), v in counter.items() if l == 'local')
        global_n = sum(v for (l, *_), v in counter.items() if l == 'global')
        en_n = sum(v for (_, lg, *_), v in counter.items() if lg == 'en')
        ar_n = sum(v for (_, lg, *_), v in counter.items() if lg == 'ar')
        print(f'\n  local={local_n}  global={global_n}  en={en_n}  ar={ar_n}')

    countTable(rows_train, 'TRAIN')
    countTable(rows_test, 'TEST')
    print(f'\nTotal rows: {len(rows_train) + len(rows_test)}  |  Dropped duplicates: {dropped}')


def spotCheck(rows_train):
    def sample(rows, label, lang, n=5):
        pool = [r for r in rows if r['label'] == label and r['lang'] == lang]
        return random.sample(pool, min(n, len(pool)))

    print('\n=== SPOT CHECK ===')
    print('\n-- 5 AR-local --')
    for r in sample(rows_train, 'local', 'ar'):
        print(' ', r['text'])
    print('\n-- 5 AR-global --')
    for r in sample(rows_train, 'global', 'ar'):
        print(' ', r['text'])
    print('\n-- 5 EN-global (template source) --')
    pool = [r for r in rows_train if r['label'] == 'global' and r['lang'] == 'en' and r['source'] in ('template', 'apnews_graph', '2wiki_graph', 'cbe_en_docs')]
    for r in random.sample(pool, min(5, len(pool))):
        print(' ', r['text'])


if __name__ == '__main__':
    main()
