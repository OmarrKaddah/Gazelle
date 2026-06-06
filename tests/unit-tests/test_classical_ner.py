"""Unit tests for classical_NER: featureExtract, runCrf, evalNer pure functions."""
import sys
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Mock CAMeL Tools BEFORE any classical_NER import — the tagger loads at module level.
_camel = MagicMock()
for _mod in [
    'camel_tools',
    'camel_tools.disambig',
    'camel_tools.disambig.mle',
    'camel_tools.tagger',
    'camel_tools.tagger.default',
]:
    sys.modules.setdefault(_mod, _camel)

_NER_SRC = str(Path(__file__).parent.parent.parent / 'src' / 'classical_NER')
if _NER_SRC not in sys.path:
    sys.path.insert(0, _NER_SRC)

import featureExtract  # noqa: E402
from featureExtract import (  # noqa: E402
    isArabic,
    tokenize,
    bioAlign,
    morphFeatures,
    scriptFeatures,
    charNgrams,
    contextTriggerFeatures,
)
from runCrf import bioToSpans  # noqa: E402
from evalNer import toSpanSet, computeF1  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def work_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# isArabic
# ---------------------------------------------------------------------------

class TestIsArabic:
    def test_pure_arabic(self):
        assert isArabic('البنك المركزي المصري') is True

    def test_pure_latin(self):
        assert isArabic('Central Bank of Egypt') is False

    def test_empty_string(self):
        assert isArabic('') is False

    def test_mostly_arabic_with_latin(self):
        # 'البنك CBE' — Arabic chars dominate
        assert isArabic('البنك CBE') is True

    def test_mostly_latin_fails(self):
        assert isArabic('a' * 50 + 'ب') is False

    def test_custom_threshold(self):
        # 1 Arabic char, 9 Latin chars → 10%
        text = 'ب' + 'a' * 9
        assert isArabic(text, threshold=0.10) is True
        assert isArabic(text, threshold=0.11) is False


# ---------------------------------------------------------------------------
# tokenize
# ---------------------------------------------------------------------------

class TestTokenize:
    def test_arabic_words(self):
        tokens = tokenize('بنك مصر')
        assert len(tokens) == 2
        assert tokens[0]['word'] == 'بنك'
        assert tokens[1]['word'] == 'مصر'

    def test_offsets_correct(self):
        tokens = tokenize('بنك مصر')
        assert tokens[0]['start'] == 0
        assert tokens[0]['end'] == 3
        assert tokens[1]['start'] == 4
        assert tokens[1]['end'] == 7

    def test_latin_date_range_single_token(self):
        tokens = tokenize('2020-2021')
        assert len(tokens) == 1
        assert tokens[0]['word'] == '2020-2021'

    def test_arabic_date_range_single_token(self):
        tokens = tokenize('١٩٩٩-٢٠٠٠')
        assert len(tokens) == 1

    def test_empty_string(self):
        assert tokenize('') == []

    def test_punctuation_separate_token(self):
        tokens = tokenize('بنك.')
        words = [t['word'] for t in tokens]
        assert '.' in words


# ---------------------------------------------------------------------------
# bioAlign
# ---------------------------------------------------------------------------

class TestBioAlign:
    def _tok(self, word, start, end):
        return {'word': word, 'start': start, 'end': end}

    def test_no_spans_all_O(self):
        tokens = [self._tok('كلمة', 0, 4), self._tok('أخرى', 5, 9)]
        assert bioAlign(tokens, []) == ['O', 'O']

    def test_single_token_entity(self):
        tokens = [self._tok('مصر', 0, 3)]
        assert bioAlign(tokens, [{'start': 0, 'end': 3, 'type': 'LOC'}]) == ['B']

    def test_multi_token_entity(self):
        tokens = [self._tok('البنك', 0, 5), self._tok('المركزي', 6, 13)]
        labels = bioAlign(tokens, [{'start': 0, 'end': 13, 'type': 'ORG'}])
        assert labels == ['B', 'I']

    def test_two_separate_entities(self):
        tokens = [
            self._tok('مصر', 0, 3),
            self._tok('في', 4, 6),
            self._tok('القاهرة', 7, 14),
        ]
        labels = bioAlign(tokens, [
            {'start': 0, 'end': 3, 'type': 'LOC'},
            {'start': 7, 'end': 14, 'type': 'LOC'},
        ])
        assert labels == ['B', 'O', 'B']

    def test_three_token_span(self):
        tokens = [
            self._tok('البنك', 0, 5),
            self._tok('المركزي', 6, 13),
            self._tok('المصري', 14, 20),
        ]
        labels = bioAlign(tokens, [{'start': 0, 'end': 20, 'type': 'ORG'}])
        assert labels == ['B', 'I', 'I']


# ---------------------------------------------------------------------------
# morphFeatures
# ---------------------------------------------------------------------------

class TestMorphFeatures:
    def test_definite_article(self):
        f = morphFeatures('البنك')
        assert f['has_def_art'] is True
        assert f['stem'] == 'بنك'

    def test_bal_prefix_strips_prep_and_article_together(self):
        # 'بال' is consumed as a prep_prefix; stem becomes 'بنك' (no ال left)
        f = morphFeatures('بالبنك')
        assert f['has_prep_clitic'] is True
        assert f['has_def_art'] is False
        assert f['stem'] == 'بنك'

    def test_plain_word_no_clitics(self):
        # 'هيئة' starts with ه — not in prep_clitics (ب ل ك و ف)
        f = morphFeatures('هيئة')
        assert f['has_def_art'] is False
        assert f['has_prep_clitic'] is False
        assert f['stem'] == 'هيئة'

    def test_prep_clitic_b(self):
        f = morphFeatures('بمصر')
        assert f['has_prep_clitic'] is True


# ---------------------------------------------------------------------------
# scriptFeatures
# ---------------------------------------------------------------------------

class TestScriptFeatures:
    def test_arabic_numerals(self):
        f = scriptFeatures('٢٠٢٣')
        assert f['is_arabic_num'] is True
        assert f['is_western_num'] is False

    def test_western_numerals(self):
        f = scriptFeatures('2023')
        assert f['is_western_num'] is True
        assert f['is_arabic_num'] is False

    def test_contains_latin(self):
        f = scriptFeatures('CBE')
        assert f['contains_latin'] is True

    def test_clause_ref(self):
        f = scriptFeatures('2-3-4')
        assert f['is_clause_ref'] is True

    def test_abbreviation(self):
        f = scriptFeatures('CBE')
        assert f['is_abbreviation'] is True

    def test_plain_arabic_word_all_false(self):
        f = scriptFeatures('بنك')
        assert f['is_arabic_num'] is False
        assert f['is_western_num'] is False
        assert f['contains_latin'] is False
        assert f['is_clause_ref'] is False
        assert f['is_abbreviation'] is False


# ---------------------------------------------------------------------------
# charNgrams
# ---------------------------------------------------------------------------

class TestCharNgrams:
    def test_two_char_word(self):
        f = charNgrams('مص')
        assert 'c2_مص' in f
        assert not any(k.startswith('c3_') for k in f)

    def test_three_char_word(self):
        f = charNgrams('مصر')
        bigrams  = [k for k in f if k.startswith('c2_')]
        trigrams = [k for k in f if k.startswith('c3_')]
        assert len(bigrams) == 2
        assert len(trigrams) == 1

    def test_single_char_empty(self):
        assert charNgrams('م') == {}


# ---------------------------------------------------------------------------
# contextTriggerFeatures
# ---------------------------------------------------------------------------

class TestContextTriggerFeatures:
    ORG    = {'بنك', 'شركة'}
    MONEY  = {'جنيه', 'مليون'}
    MONTHS = {'يناير', 'فبراير'}

    def test_org_trigger(self):
        f = contextTriggerFeatures('بنك', self.ORG, self.MONEY, self.MONTHS)
        assert f['is_org_trigger'] is True
        assert f['in_money_trigger'] is False

    def test_money_trigger(self):
        f = contextTriggerFeatures('مليون', self.ORG, self.MONEY, self.MONTHS)
        assert f['in_money_trigger'] is True

    def test_month_trigger(self):
        f = contextTriggerFeatures('يناير', self.ORG, self.MONEY, self.MONTHS)
        assert f['in_month'] is True

    def test_no_trigger(self):
        f = contextTriggerFeatures('الكلمة', self.ORG, self.MONEY, self.MONTHS)
        assert not any(f.values())


# ---------------------------------------------------------------------------
# bioToSpans
# ---------------------------------------------------------------------------

class TestBioToSpans:
    def _tok(self, word, start, end):
        return {'word': word, 'start': start, 'end': end}

    def test_empty(self):
        assert bioToSpans([], [], 'c1', 'doc') == []

    def test_all_O(self):
        tokens = [self._tok('كلمة', 0, 4)]
        assert bioToSpans(tokens, ['O'], 'c1', 'doc') == []

    def test_single_B(self):
        tokens = [self._tok('مصر', 0, 3)]
        spans = bioToSpans(tokens, ['B'], 'c1', 'doc')
        assert len(spans) == 1
        assert spans[0]['text'] == 'مصر'
        assert spans[0]['start'] == 0
        assert spans[0]['end'] == 3
        assert spans[0]['score'] == 1.0

    def test_type_equals_text(self):
        tokens = [self._tok('مصر', 0, 3)]
        spans = bioToSpans(tokens, ['B'], 'c1', 'doc')
        assert spans[0]['type'] == spans[0]['text']

    def test_B_I_merged(self):
        tokens = [self._tok('البنك', 0, 5), self._tok('المركزي', 6, 13)]
        spans = bioToSpans(tokens, ['B', 'I'], 'c1', 'doc')
        assert len(spans) == 1
        assert spans[0]['text'] == 'البنك المركزي'
        assert spans[0]['end'] == 13

    def test_two_separate_entities(self):
        tokens = [self._tok('مصر', 0, 3), self._tok('في', 4, 6), self._tok('القاهرة', 7, 14)]
        spans = bioToSpans(tokens, ['B', 'O', 'B'], 'c1', 'doc')
        assert len(spans) == 2
        assert spans[0]['text'] == 'مصر'
        assert spans[1]['text'] == 'القاهرة'

    def test_I_without_preceding_B_ignored(self):
        tokens = [self._tok('البنك', 0, 5), self._tok('المركزي', 6, 13)]
        spans = bioToSpans(tokens, ['O', 'I'], 'c1', 'doc')
        assert spans == []

    def test_trailing_entity_flushed(self):
        tokens = [self._tok('مصر', 0, 3), self._tok('العربية', 4, 11)]
        spans = bioToSpans(tokens, ['B', 'I'], 'c1', 'doc')
        assert len(spans) == 1
        assert spans[0]['text'] == 'مصر العربية'

    def test_chunk_and_doc_propagated(self):
        tokens = [self._tok('مصر', 0, 3)]
        spans = bioToSpans(tokens, ['B'], 'Chapter_1-c001', 'Chapter_1')
        assert spans[0]['chunkId'] == 'Chapter_1-c001'
        assert spans[0]['docName'] == 'Chapter_1'

    def test_gliner_compatible_fields(self):
        tokens = [self._tok('مصر', 0, 3)]
        spans = bioToSpans(tokens, ['B'], 'c1', 'doc')
        required = {'chunkId', 'docName', 'text', 'type', 'start', 'end', 'score'}
        assert required.issubset(spans[0].keys())


# ---------------------------------------------------------------------------
# dumpEntities
# Note: current implementation writes {EXTRACT_DIR}/{docName}_entities.json
# (modelName is accepted but not used in the path).
# ---------------------------------------------------------------------------

class TestDumpEntities:
    def _entity(self, text='البنك'):
        return {'chunkId': 'c1', 'docName': 'doc', 'text': text,
                'type': text, 'start': 0, 'end': len(text), 'score': 1.0}

    def test_creates_output_file(self, tmp_path):
        import runCrf
        with patch.object(runCrf, 'EXTRACT_DIR', str(tmp_path)):
            runCrf.dumpEntities([self._entity()], 'my_doc', 'crf_bank')
        assert (tmp_path / 'my_doc_entities.json').exists()

    def test_creates_extract_dir(self, tmp_path):
        import runCrf
        outdir = tmp_path / 'extractions'
        with patch.object(runCrf, 'EXTRACT_DIR', str(outdir)):
            runCrf.dumpEntities([], 'doc', 'crf')
        assert outdir.exists()

    def test_unicode_preserved(self, tmp_path):
        import runCrf
        with patch.object(runCrf, 'EXTRACT_DIR', str(tmp_path)):
            runCrf.dumpEntities([self._entity('البنك المركزي')], 'doc', 'crf')
        content = (tmp_path / 'doc_entities.json').read_text(encoding='utf-8')
        assert 'البنك المركزي' in content

    def test_empty_list_valid_json(self, tmp_path):
        import runCrf
        with patch.object(runCrf, 'EXTRACT_DIR', str(tmp_path)):
            runCrf.dumpEntities([], 'doc', 'crf')
        saved = json.loads((tmp_path / 'doc_entities.json').read_text())
        assert saved == []


# ---------------------------------------------------------------------------
# toSpanSet / computeF1
# ---------------------------------------------------------------------------

class TestToSpanSet:
    def test_basic_conversion(self):
        entities = [
            {'chunkId': 'c1', 'start': 0, 'end': 5, 'text': 'مصر', 'type': 'مصر'},
            {'chunkId': 'c1', 'start': 10, 'end': 20, 'text': 'البنك', 'type': 'البنك'},
        ]
        s = toSpanSet(entities)
        assert ('c1', 0, 5) in s
        assert ('c1', 10, 20) in s

    def test_deduplication(self):
        entities = [
            {'chunkId': 'c1', 'start': 0, 'end': 5, 'text': 'مصر', 'type': 'مصر'},
            {'chunkId': 'c1', 'start': 0, 'end': 5, 'text': 'مصر', 'type': 'مصر'},
        ]
        assert len(toSpanSet(entities)) == 1


class TestComputeF1:
    def test_perfect_match(self):
        s = {('c1', 0, 5)}
        p, r, f1, tp, fp, fn = computeF1(s, s)
        assert p == 1.0 and r == 1.0 and f1 == 1.0 and tp == 1

    def test_no_overlap(self):
        gold = {('c1', 0, 5)}
        pred = {('c1', 6, 10)}
        p, r, f1, tp, fp, fn = computeF1(gold, pred)
        assert f1 == 0.0 and tp == 0 and fp == 1 and fn == 1

    def test_partial_precision_recall(self):
        gold = {('c1', 0, 5), ('c1', 10, 20)}
        pred = {('c1', 0, 5), ('c1', 30, 40)}
        p, r, f1, tp, fp, fn = computeF1(gold, pred)
        assert tp == 1 and fp == 1 and fn == 1
        assert abs(f1 - 0.5) < 1e-9

    def test_both_empty(self):
        p, r, f1, tp, fp, fn = computeF1(set(), set())
        assert f1 == 0.0
