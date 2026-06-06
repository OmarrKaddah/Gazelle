import re


GLOBAL_CUES_AR = ['اتجاه', 'اتجاهات', 'موضوعات', 'مواضيع', 'بشكل عام', 'بصفه عام',
                  'عبر الوثائق', 'عبر المستندات', 'عبر المجموعه', 'نمط', 'انماط',
                  'ملخص', 'لخص', 'عموما', 'المتكرره', 'ككل', 'الرئيسيه',
                  'الصوره العامه', 'القضايا الرئيسيه']
GLOBAL_CUES_EN = ['across', 'overall', 'theme', 'themes', 'trend', 'trends',
                  'pattern', 'patterns', 'summary', 'summarize', 'broadly',
                  'general', 'recurring', 'throughout', 'landscape', 'narrative',
                  'as a whole', 'main themes', 'corpus-wide']

LOCAL_CUES_AR = ['ما هو', 'ما هي', 'من هو', 'متى', 'اين', 'كم', 'تعريف', 'عرف',
                 'قيمه', 'ما المقصود', 'دور', 'متطلبات', 'الشروط']
LOCAL_CUES_EN = ['what is', 'who is', 'when', 'where', 'how much', 'how many',
                 'define', 'definition', 'value of', 'located', 'which']

COMPARISON_CUES = ['compare', 'comparison', 'versus', 'vs', 'difference between',
                   'قارن', 'مقارنه', 'مقابل', 'بين']
AGGREGATE_CUES = ['most', 'all', 'every', 'main', 'major', 'entire', 'whole',
                  'جميع', 'كل', 'معظم', 'ابرز', 'العامه', 'الرئيسيه', 'كافه']

WHEN_CUES = ['when', 'متى']
WHERE_CUES = ['where', 'اين']
WHO_CUES = ['who', 'من هو', 'من هي']
QUANTITY_CUES = ['how much', 'how many', 'كم']
DEFINE_CUES = ['define', 'definition', 'تعريف', 'عرف', 'ما المقصود']





GLOBAL_CUES = GLOBAL_CUES_AR + GLOBAL_CUES_EN
LOCAL_CUES = LOCAL_CUES_AR + LOCAL_CUES_EN







HARAKAT = re.compile(r'[ً-ْٰـ]')
TOKEN = re.compile(r'[\w؀-ۿ]+')
DIGIT = re.compile(r'[0-9٠-٩]')










FEATURE_NAMES = ['globalCueRatio', 'localCueRatio', 'globalCuePresent',
                 'localCuePresent', 'cueDiff', 'tokenCount', 'hasDigit',
                 'hasComparison', 'hasAggregate', 'hasWhen', 'hasWhere',
                 'hasWho', 'hasQuantity', 'hasDefine']

















def normalizeArabic(text):
    text = HARAKAT.sub('', text)
    text = re.sub('[أإآٱ]', 'ا', text)
    text = text.replace('ى', 'ي').replace('ة', 'ه')
    return text













def normalizeText(text):

    return normalizeArabic(text.lower())


def isArabic(text):

    return any('؀' <= c <= 'ۿ' for c in text)


def cueCount(textNorm, cue):

    if isArabic(cue):

        return textNorm.count(cue)
    return len(re.findall(r'\b' + re.escape(cue) + r'\b', textNorm))



def totalHits(textNorm, cues):

    return sum(cueCount(textNorm, c) for c in cues)




def anyHit(textNorm, cues):
    return 1.0 if totalHits(textNorm, cues) else 0.0





def cueFeatures(query):
    norm = normalizeText(query)
    tokens = TOKEN.findall(norm)
    n = len(tokens)
    globalHits = totalHits(norm, GLOBAL_CUES)
    localHits = totalHits(norm, LOCAL_CUES)
    return [
        globalHits / n if n else 0.0,
        localHits / n if n else 0.0,
        1.0 if globalHits else 0.0,
        1.0 if localHits else 0.0,
        float(globalHits - localHits),
        float(n),
        1.0 if DIGIT.search(query) else 0.0,
        anyHit(norm, COMPARISON_CUES),
        anyHit(norm, AGGREGATE_CUES),
        anyHit(norm, WHEN_CUES),
        anyHit(norm, WHERE_CUES),
        anyHit(norm, WHO_CUES),
        anyHit(norm, QUANTITY_CUES),
        anyHit(norm, DEFINE_CUES),
    ]


if __name__ == '__main__':
    samples = [
        'ما هي الاتجاهات العامة فيما يخص الشمول المالي عبر الوثائق؟',
        'ما هو الحد الأدنى لكفاية رأس المال؟',
        'What are the main themes related to financial inclusion across the documents?',
        'How much is the minimum capital adequacy ratio?',
    ]
    for s in samples:
        feats = cueFeatures(s)
        print(s)
        print({k: round(v, 3) for k, v in zip(FEATURE_NAMES, feats)})
        print()
