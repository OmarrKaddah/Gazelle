"""Module tests for the classical_NER pipeline:
featureExtract → CRF inference → evalNer interactions.
"""
import sys
import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Mock CAMeL Tools BEFORE any classical_NER import
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
from featureExtract import tokenize, bioAlign, extractChunk, isArabic  # noqa: E402
from runCrf import bioToSpans, predictChunk, dumpEntities  # noqa: E402
from evalNer import toSpanSet, computeF1, loadGold, loadCrf  # noqa: E402


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def work_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


ARABIC_CHUNK = {
    'chunkId': 'Chapter_1-c0001',
    'docName': 'Chapter_1',
    'text': 'يمارس البنك المركزي المصري رقابته على البنوك التجارية وفقاً للقانون.',
}

ENGLISH_CHUNK = {
    'chunkId': 'Chapter_1-c0002',
    'docName': 'Chapter_1',
    'text': 'This paragraph is entirely in English with no Arabic content whatsoever.',
}

ORG_T   = {'بنك', 'شركة', 'هيئة', 'وزارة', 'مؤسسة'}
MONEY_T = {'جنيه', 'دولار', 'يورو', 'مليار', 'مليون', 'ألف', 'جنيهاً', 'دولاراً'}
MONTHS  = {'يناير', 'فبراير', 'مارس', 'إبريل', 'أبريل', 'مايو', 'يونيو',
           'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر'}


# ---------------------------------------------------------------------------
# Arabic language filter
# ---------------------------------------------------------------------------

class TestArabicFilter:
    def test_arabic_chunk_passes_isArabic(self):
        assert isArabic(ARABIC_CHUNK['text']) is True

    def test_english_chunk_blocked_by_isArabic(self):
        assert isArabic(ENGLISH_CHUNK['text']) is False

    def test_predict_chunk_returns_empty_for_english(self):
        mock_crf = MagicMock()
        featureExtract._tagger.tag.return_value = []
        result = predictChunk(mock_crf, ENGLISH_CHUNK, ORG_T, MONEY_T, MONTHS)
        assert result == []
        mock_crf.predict.assert_not_called()


# ---------------------------------------------------------------------------
# Money / month filter applied inside predictChunk
# ---------------------------------------------------------------------------

class TestMoneyMonthFilter:
    def _run_single_word_chunk(self, word, label):
        chunk = {'chunkId': 'c1', 'docName': 'doc', 'text': word}
        mock_crf = MagicMock()
        featureExtract._tagger.tag.return_value = ['NN']
        mock_crf.predict.return_value = [[label]]
        return predictChunk(mock_crf, chunk, ORG_T, MONEY_T, MONTHS)

    def test_money_trigger_word_not_in_output(self):
        spans = self._run_single_word_chunk('مليون', 'B')
        assert spans == []

    def test_month_name_not_in_output(self):
        spans = self._run_single_word_chunk('يناير', 'B')
        assert spans == []

    def test_real_entity_survives_filter(self):
        spans = self._run_single_word_chunk('البنك', 'B')
        assert len(spans) == 1
        assert spans[0]['text'] == 'البنك'

    def test_multi_word_money_phrase_dropped(self):
        chunk = {'chunkId': 'c1', 'docName': 'doc', 'text': 'مليون جنيه'}
        mock_crf = MagicMock()
        featureExtract._tagger.tag.return_value = ['NN', 'NN']
        mock_crf.predict.return_value = [['B', 'B']]
        spans = predictChunk(mock_crf, chunk, ORG_T, MONEY_T, MONTHS)
        # each word is its own span; both are money triggers
        assert spans == []


# ---------------------------------------------------------------------------
# BIO alignment → feature extraction pipeline
# ---------------------------------------------------------------------------

class TestBioAlignPipeline:
    def test_tokenize_then_align_produces_B_before_I(self):
        # 'البنك'(0-5) 'المركزي'(6-13) — span covers both tokens exactly
        text = 'البنك المركزي يشرف'
        spans = [{'start': 0, 'end': 13, 'type': 'ORG'}]
        tokens = tokenize(text)
        labels = bioAlign(tokens, spans)
        assert 'B' in labels
        assert 'I' in labels
        assert labels.index('B') < labels.index('I')

    def test_extractChunk_produces_feature_label_pairs(self):
        text = 'البنك المركزي يشرف'
        spans = [{'start': 0, 'end': 13, 'type': 'ORG'}]
        featureExtract._tagger.tag.return_value = ['NN', 'NN', 'VB']
        pairs = extractChunk(text, spans, ORG_T, MONEY_T, MONTHS)
        assert len(pairs) == 3
        feats0, label0 = pairs[0]
        feats1, label1 = pairs[1]
        feats2, label2 = pairs[2]
        assert label0 == 'B'
        assert label1 == 'I'
        assert label2 == 'O'

    def test_extractChunk_features_contain_required_keys(self):
        text = 'البنك يشرف'
        spans = [{'start': 0, 'end': 5, 'type': 'ORG'}]
        featureExtract._tagger.tag.return_value = ['NN', 'VB']
        pairs = extractChunk(text, spans, ORG_T, MONEY_T, MONTHS)
        feats, _ = pairs[0]
        for key in ('word', 'pos', 'w-1', 'w+1', 'w-2', 'w+2',
                    'has_def_art', 'is_org_trigger'):
            assert key in feats, f"missing feature: {key}"

    def test_entity_tokens_use_context_window(self):
        text = 'في البنك المركزي اليوم'
        spans = [{'start': 3, 'end': 16, 'type': 'ORG'}]
        featureExtract._tagger.tag.return_value = ['PREP', 'NN', 'NN', 'NN']
        pairs = extractChunk(text, spans, ORG_T, MONEY_T, MONTHS)
        # Token at index 1 ('البنك') should have w-1 = 'في'
        feats_b = pairs[1][0]
        assert feats_b['w-1'] == 'في'


# ---------------------------------------------------------------------------
# Evaluation pipeline: load → F1
# ---------------------------------------------------------------------------

class TestEvalNerPipeline:
    def test_perfect_f1(self):
        spans = [{'chunkId': 'c1', 'start': 0, 'end': 5, 'text': 'مصر', 'type': 'مصر'}]
        gs = toSpanSet(spans)
        _, _, f1, _, _, _ = computeF1(gs, gs)
        assert f1 == 1.0

    def test_partial_recall(self):
        gold = [
            {'chunkId': 'c1', 'start': 0, 'end': 5, 'text': 'مصر', 'type': 'مصر'},
            {'chunkId': 'c1', 'start': 10, 'end': 20, 'text': 'البنك', 'type': 'البنك'},
        ]
        pred = [{'chunkId': 'c1', 'start': 0, 'end': 5, 'text': 'مصر', 'type': 'مصر'}]
        gs = toSpanSet(gold)
        ps = toSpanSet(pred)
        p, r, f1, tp, fp, fn = computeF1(gs, ps)
        assert p == 1.0 and r < 1.0 and fn == 1

    def test_loadGold_from_file(self, work_dir):
        gold_data = [{'chunkId': 'c1', 'start': 0, 'end': 5, 'text': 'مصر', 'type': 'مصر'}]
        (work_dir / 'annotations').mkdir()
        (work_dir / 'annotations' / 'gold_test_doc.json').write_text(
            json.dumps(gold_data), encoding='utf-8'
        )
        loaded = loadGold('test_doc')
        assert loaded == gold_data

    def test_loadCrf_from_flat_extractions_path(self, work_dir):
        pred_data = [{'chunkId': 'c1', 'start': 0, 'end': 5, 'text': 'مصر', 'type': 'مصر'}]
        (work_dir / 'extractions').mkdir()
        (work_dir / 'extractions' / 'test_doc_crf_bank_entities.json').write_text(
            json.dumps(pred_data), encoding='utf-8'
        )
        loaded = loadCrf('test_doc', 'crf_bank')
        assert loaded == pred_data

    def test_full_eval_round_trip(self, work_dir):
        gold_data = [
            {'chunkId': 'c1', 'start': 0, 'end': 5, 'text': 'مصر', 'type': 'مصر'},
            {'chunkId': 'c2', 'start': 10, 'end': 25, 'text': 'البنك المركزي', 'type': 'البنك المركزي'},
        ]
        pred_data = [
            {'chunkId': 'c1', 'start': 0, 'end': 5, 'text': 'مصر', 'type': 'مصر'},
        ]
        (work_dir / 'annotations').mkdir()
        (work_dir / 'annotations' / 'gold_chapter.json').write_text(
            json.dumps(gold_data), encoding='utf-8'
        )
        (work_dir / 'extractions').mkdir()
        (work_dir / 'extractions' / 'chapter_crf_bank_entities.json').write_text(
            json.dumps(pred_data), encoding='utf-8'
        )
        gold = loadGold('chapter')
        pred = loadCrf('chapter', 'crf_bank')
        gs = toSpanSet(gold)
        ps = toSpanSet(pred)
        p, r, f1, tp, fp, fn = computeF1(gs, ps)
        assert tp == 1 and fn == 1 and fp == 0
        assert p == 1.0
        assert abs(r - 0.5) < 1e-9


# ---------------------------------------------------------------------------
# Output format compatibility with GLiNER
# ---------------------------------------------------------------------------

class TestOutputFormat:
    def test_bioToSpans_has_all_gliner_fields(self):
        tokens = [
            {'word': 'البنك', 'start': 0, 'end': 5},
            {'word': 'المركزي', 'start': 6, 'end': 13},
        ]
        spans = bioToSpans(tokens, ['B', 'I'], 'Chapter_1-c001', 'Chapter_1')
        required = {'chunkId', 'docName', 'text', 'type', 'start', 'end', 'score'}
        assert required.issubset(spans[0].keys())

    def test_type_equals_entity_text(self):
        tokens = [{'word': 'البنك', 'start': 0, 'end': 5}]
        spans = bioToSpans(tokens, ['B'], 'c1', 'doc')
        assert spans[0]['type'] == spans[0]['text']

    def test_score_is_float(self):
        tokens = [{'word': 'مصر', 'start': 0, 'end': 3}]
        spans = bioToSpans(tokens, ['B'], 'c1', 'doc')
        assert isinstance(spans[0]['score'], float)

    def test_dumpEntities_writes_correct_entity_data(self, tmp_path):
        import runCrf
        from unittest.mock import patch
        tokens = [
            {'word': 'البنك', 'start': 0, 'end': 5},
            {'word': 'المركزي', 'start': 6, 'end': 13},
        ]
        entities = bioToSpans(tokens, ['B', 'I'], 'c1', 'Chapter_1')
        with patch.object(runCrf, 'EXTRACT_DIR', str(tmp_path)):
            dumpEntities(entities, 'Chapter_1', 'crf_bank')
        saved = json.loads((tmp_path / 'Chapter_1_entities.json').read_text(encoding='utf-8'))
        assert len(saved) == 1
        assert saved[0]['text'] == 'البنك المركزي'
        assert saved[0]['type'] == 'البنك المركزي'
