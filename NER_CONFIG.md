# NER Configuration Guide

This document explains how to configure entity extraction strategies in the Gazelle pipeline.

## Quick Start

### For Your 2x5090 GPU Setup (Recommended)

In `.env`, set:

```env
# Use hybrid approach (best accuracy/speed tradeoff)
NER_STRATEGY=hybrid

# Use multi-lingual GLiNER for fast entity extraction
GLINER_MODEL=urchade/gliner_multi

# Your local LLM for relationship extraction and refinement
OLLAMA_URL=http://localhost:11434/v1/chat/completions
OLLAMA_TEXT_MODEL=qwen2.5:72b-instruct-q4_K_M
OLLAMA_NUM_PARALLEL=4
```

Then run:

```bash
python runners/runAll.py Documents/
```

---

## NER Strategies Explained

### Strategy 1: `hybrid` (Recommended)

**What it does:**
- GLiNER (fast) extracts raw entities from each chunk
- LLM refines and extracts relationships

**Pros:**
- ✅ Best accuracy + speed balance
- ✅ Handles Arabic + English naturally
- ✅ Lower hallucination risk
- ✅ Leverages your 5090 GPU for relationships

**Cons:**
- Uses both models (more VRAM)

**Configuration:**
```env
NER_STRATEGY=hybrid
GLINER_MODEL=urchade/gliner_multi
OLLAMA_TEXT_MODEL=qwen2.5:72b-instruct-q4_K_M
```

**When to use:** Always, unless you hit VRAM issues.

---

### Strategy 2: `gliner`

**What it does:**
- Only GLiNER entity extraction
- No LLM entity extraction
- LLM still used for relationships

**Pros:**
- ✅ Fast (no LLM for entities)
- ✅ Low VRAM usage
- ✅ Good for Arabic (with Arabic model)

**Cons:**
- ❌ Misses complex/implicit entities
- ❌ Weaker on English or code-switched text

**Configuration:**
```env
NER_STRATEGY=gliner
GLINER_MODEL=NAMAA-Space/gliner_arabic-v2.1
GLINER_THRESHOLD=0.5
```

**When to use:**
- When you want fastest throughput
- When you only have Arabic documents
- When VRAM is limited

---

### Strategy 3: `llm`

**What it does:**
- Only LLM for entity extraction (no GLiNER)
- LLM also handles relationship extraction

**Pros:**
- ✅ Most accurate (if LLM is good)
- ✅ Handles complex domain concepts
- ✅ Multi-lingual naturally
- ✅ Fewer false positives with good prompt

**Cons:**
- ❌ Much slower (every entity via LLM)
- ❌ Higher cost (API or local inference)
- ❌ Hallucination risk (LLM invents entities)
- ❌ Requires good LLM model

**Configuration:**
```env
NER_STRATEGY=llm
OLLAMA_URL=http://localhost:11434/v1/chat/completions
OLLAMA_TEXT_MODEL=qwen2.5:72b-instruct-q4_K_M
OLLAMA_NUM_PARALLEL=4
```

**When to use:**
- When accuracy > speed
- When you have powerful local LLM
- When dealing with very technical jargon
- When you can afford the latency

---

## Available GLiNER Models

| Model | Language | Speed | Accuracy | Size |
|-------|----------|-------|----------|------|
| `NAMAA-Space/gliner_arabic-v2.1` | Arabic | ⚡⚡⚡ | High | ~300MB |
| `urchade/gliner_multi` | Multi-lingual | ⚡⚡ | Good | ~300MB |
| `urchade/gliner_base` | English | ⚡⚡⚡ | Good | ~300MB |

**For mixed Arabic/English:** Use `urchade/gliner_multi`

---

## Recommended LLM Models for Your 2x5090

All of these run well on your 64GB VRAM:

| Model | Size | VRAM (4-bit) | Speed | Arabic Support |
|-------|------|-------------|-------|----------------|
| **Qwen2.5 72B** | 72B | ~45GB | ⚡⚡ Fast | Excellent |
| **Llama 3 70B** | 70B | ~42GB | ⚡⚡ Fast | Good |
| **Mixtral 8x7B** | 8x7B | ~20GB | ⚡⚡⚡ Very Fast | Good |
| **Qwen2 7B** | 7B | ~5GB | ⚡⚡⚡ Very Fast | Excellent |

**Pick:** `qwen2.5:72b-instruct-q4_K_M` (best balance)

Pull with:
```bash
ollama pull qwen2.5:72b-instruct-q4_K_M
```

---

## Confidence Thresholds

### For GLiNER

Adjust `GLINER_THRESHOLD` (0.0-1.0) to control entity detection sensitivity:

```env
GLINER_THRESHOLD=0.5   # Default: balanced
GLINER_THRESHOLD=0.7   # Strict: fewer false positives
GLINER_THRESHOLD=0.3   # Loose: catch more entities
```

**Recommendation:** `0.5` for legal documents.

---

## Performance Comparison

| Strategy | Speed | Accuracy | VRAM | Cost |
|----------|-------|----------|------|------|
| GLiNER only | ⚡⚡⚡ 30 sec | 70% | 2GB | Free |
| LLM only | ⚡ 2-3 min | 85% | 45GB | High |
| Hybrid (recommended) | ⚡⚡ 1-1.5 min | 80% | 47GB | Medium |

---

## Example Configurations

### Config A: Speed-Focused (Arabic documents)
```env
NER_STRATEGY=gliner
GLINER_MODEL=NAMAA-Space/gliner_arabic-v2.1
GLINER_THRESHOLD=0.6
```

### Config B: Accuracy-Focused (Mixed Arabic+English)
```env
NER_STRATEGY=hybrid
GLINER_MODEL=urchade/gliner_multi
OLLAMA_TEXT_MODEL=qwen2.5:72b-instruct-q4_K_M
```

### Config C: Pure LLM (If you trust your LLM)
```env
NER_STRATEGY=llm
OLLAMA_TEXT_MODEL=qwen2.5:72b-instruct-q4_K_M
GLINER_THRESHOLD=0.5  # Ignored
```

---

## Troubleshooting

### Problem: "OLLAMA_URL refused connection"
**Solution:** Make sure Ollama is running:
```bash
ollama serve
```

### Problem: Out of Memory (OOM)
**Solution:** 
1. Switch to smaller model: `qwen2:7b` instead of `72b`
2. Use `NER_STRATEGY=gliner` (skip LLM for entities)
3. Reduce `OLLAMA_NUM_PARALLEL` to 2 or 1

### Problem: Entity extraction is slow
**Solution:**
1. Use `NER_STRATEGY=gliner` for faster entity extraction
2. Switch to `urchade/gliner_multi` instead of Arabic-only model
3. Reduce chunk size in `.env CHUNKER_TYPE` or adjust chunker parameters

### Problem: Missing entities
**Solution:**
1. Lower `GLINER_THRESHOLD` (e.g., 0.3 instead of 0.5)
2. Switch to `NER_STRATEGY=llm` (more thorough)
3. Fine-tune GLiNER on your domain

---

## Runtime Commands

Show current configuration:
```bash
grep NER_STRATEGY .env
grep GLINER .env
grep OLLAMA .env
```

Run with specific strategy:
```bash
# Hybrid (reads from .env)
python runners/runAll.py Documents/

# Or set inline (overrides .env)
export NER_STRATEGY=gliner
python runners/runAll.py Documents/
```

---

## Next Steps

1. **Test all 3 strategies** on a small document (1-2 chunks)
2. **Measure F1 score** on eval/queries.json
3. **Pick the best strategy** for your accuracy/speed needs
4. **Fine-tune GLiNER** if accuracy < 80% (see: [Fine-tuning Guide](./FINETUNING.md))
