# Gazelle — Memory Architecture

A grounded analysis of what the system stores today, why it's confused, and the
scalable design that fixes it without bloating tokens or polluting context.

This is written specifically against `src/chatApi.py`, `src/db/models.py`,
`src/db/repositories/memoryRepo.py`, and `src/db/repositories/chatRepo.py` as
they exist right now.

---

## 1. Diagnosis — what you actually have

Three tables exist for "history" today:

| Table | Granularity | Written by | Read by | What it actually contains |
|---|---|---|---|---|
| `messages` | per-turn | every `/api/chat` call | `GET /api/chats/{id}` (UI replay) | Real conversation: role, content, tokens, timestamp |
| `chat_memory` | per-chat (1:1) | `chatEventGen` after each assistant turn | nobody | `summary` (just the **last** Q/A pair, overwritten every turn) + `extractedEntities` (which is actually a list of chunkIds, not entities) + `metadata` (mode/k/hops/provider) |
| `user_memory` | per-user, key/value | `PUT /api/memory/user/{key}` only — never the chat | nobody | Free-form user-scoped facts; **never consumed by the LLM** |

### The three real bugs hiding behind your suspicion

1. **`ChatMemory.summary` is a misnomer.** `buildChatSummary()` is just
   `"User: <last q>\nAssistant: <last a>"`. It is rewritten on every turn, so
   "memory" decays to "the latest exchange" — a duplicate of the last row in
   `messages`.
2. **`ChatMemory.extractedEntities` is mislabeled.** It stores
   `{"chunkIds": [...]}` — that's a citation/provenance log, not entities.
   Real entities (the GLiNER + ontology types you have in Neo4j) are never
   written here. So if you ever wanted "what people/laws has this chat
   discussed?", the field is the wrong shape.
3. **Neither table is injected into the LLM prompt.** Look at `streamTokens()`:
   the call body is just `system_prompt + buildPrompt(query, chunks)`. No prior
   messages, no chat summary, no user prefs. **Every turn is stateless.** That's
   why follow-ups like *"and chapter 2?"* won't work — the model has no idea
   what "and" points at.

So your gut feeling that things overlap is half-right. The deeper problem is
that you have two stores that *write* memory but the inference path *reads
neither*. Memory is a side-effect, not a feature.

---

## 2. Conceptual taxonomy (use these terms consistently)

These are the five layers any production conversational AI distinguishes. Mixing
them is exactly what creates the confusion you're feeling.

| Layer | Lifetime | Granularity | Purpose | Example |
|---|---|---|---|---|
| **Retrieved context** | One turn | per-question | Document chunks fetched from your KG/vector store. The grounding evidence. | The 5 chunks the retriever returns for "متطلبات الترخيص" |
| **Session memory** | One process/login | per-token | Auth, current chat selection, UI state. Lives in cookies/JWT/Redis, not in your relational DB. | `Authorization: Bearer ...` |
| **Chat memory** | Lifetime of one chat | per-chat | Rolling summary + salient facts from THIS thread, so a 60-message chat doesn't blow the context window | "User is asking about Article 5 obligations; mentioned ADIB twice; clarified scope to retail banking" |
| **User memory** | Persistent across all chats | per-user | Stable preferences and facts that should travel between conversations | "Prefers answers in Arabic", "Compliance Analyst, retail division" |
| **Persistent / domain memory** | Forever, shared by ALL users | global | The KG itself, embeddings, ontology. Source of truth, not user-scoped. | Neo4j entities + relationships + chunk embeddings |

The bug in your current code is that **retrieved context** is well-defined
(it's the Neo4j chunks), **persistent memory** is well-defined (Neo4j itself),
**session memory** is well-defined (bearer tokens), but **chat memory** and
**user memory** are written without ever being read, and they're storing the
wrong shape of data anyway.

---

## 3. Proposed architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         PER-TURN INFERENCE                              │
│                                                                         │
│   user.query  ──►  embed  ──►  Neo4j retrieve  ──►  retrieved_chunks    │
│       │                                                       │         │
│       │                                                       ▼         │
│       │   ┌─────────────── PROMPT ASSEMBLY ─────────────────┐           │
│       │   │  SYSTEM (immutable)                             │           │
│       │   │  + USER_MEMORY  (1-3 lines, top-k by relevance) │           │
│       │   │  + CHAT_SUMMARY (rolling, ≤300 tok)             │           │
│       │   │  + LAST_N_TURNS (verbatim, e.g. last 4)         │           │
│       │   │  + CONTEXT      (retrieved chunks)              │           │
│       │   │  + QUESTION     (current user turn)             │           │
│       │   └─────────────────────────────────────────────────┘           │
│       ▼                                                                 │
│   stream answer ──►  store_message(assistant)                           │
│                  ──►  update_chat_memory (async, after turn)            │
│                  ──►  maybe_promote_to_user_memory (async, heuristic)   │
└─────────────────────────────────────────────────────────────────────────┘
```

Two principles enforce all the rules:

1. **One writer per layer.** `messages` is written by the chat endpoint.
   `chat_memory` is written by a background summarizer triggered after each
   turn. `user_memory` is written either explicitly by the user (settings page)
   or by a *promotion rule* that watches `chat_memory` and lifts patterns that
   recur across chats. Nothing else writes to those tables, ever.
2. **One reader per layer at inference time.** The prompt-assembly function in
   the chat endpoint pulls *exactly* one row from each, in a strict order, with
   a strict token budget per layer. No other code path reads them.

This is what prevents duplication and conflicts: each fact has exactly one
home, and there's a deterministic rule for which layer that home is.

---

## 4. What lives where (the assignment table)

| Fact | Lives in | Lifetime | Read by LLM? | Notes |
|---|---|---|---|---|
| Username, role, clearance | `users` | Forever | No (used for RBAC at retrieval time, not prompt) | |
| Bearer token | `user_sessions` | Until logout | No | |
| User turn text | `messages` (role='user') | Forever | **Last N only** | |
| Assistant turn text | `messages` (role='assistant') | Forever | **Last N only** | |
| Citations for an answer | `message_citations` (NEW) | Forever | No (UI only) | Move chunkIds out of `chat_memory` |
| Rolling summary of THIS chat | `chat_memory.summary` | Until chat deleted | **Yes** | Rewritten ONLY when chat exceeds N turns |
| Entities mentioned in THIS chat | `chat_memory.entities` (NEW shape) | Until chat deleted | Yes, optionally | List of `(canonicalId, type)`; used to bias retrieval, not prompt |
| User's stated preference (e.g. "answer in Arabic") | `user_memory` (memoryKey='language_pref') | Forever | **Yes** (top-k injected) | |
| User's stable role context (e.g. "retail division") | `user_memory` (memoryKey='domain_scope') | Forever | Yes | |
| Document chunks | Neo4j `Chunk` nodes | Forever | Yes (the CONTEXT block) | RBAC filtered |
| Entities & relationships | Neo4j `Entity` + edges | Forever | Indirect (used by graph retrieval mode) | |

### What should NEVER be duplicated

- **Conversation history.** Lives in `messages` only. `chat_memory.summary` is a
  *compressed* version of older turns, not a copy of recent ones.
- **Citations / chunkIds.** Lives in `message_citations` per-message. Do NOT
  also store in `chat_memory`.
- **Entities from documents.** Lives in Neo4j. `chat_memory.entities` should
  store only *references* (canonicalIds), never the entity text/type/aliases.
- **User identity facts.** Lives in `users`. Never re-store username, role, or
  clearance in `user_memory`.

---

## 5. Database schema (the proposed change)

Keep `users`, `user_sessions`, `chats`, `messages`, `audit_logs` exactly as
they are. Change `chat_memory` and `user_memory`, and add `message_citations`.

```sql
-- NEW: provenance/citations split out of chat_memory
CREATE TABLE message_citations (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  messageId    UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  chunkId      TEXT NOT NULL,                     -- e.g. 'chapter_3-c0017'
  docName      TEXT NOT NULL,
  score        REAL,
  rank         INT,
  createdAt    TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX ix_message_citations_message ON message_citations(messageId);

-- REPLACED: chat_memory is now a real rolling summary, not the last Q/A
CREATE TABLE chat_memory (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chatId          UUID NOT NULL UNIQUE REFERENCES chats(id) ON DELETE CASCADE,
  summary         TEXT NOT NULL DEFAULT '',       -- LLM-written rolling summary, ≤300 tokens
  summaryTokens   INT  NOT NULL DEFAULT 0,
  entityRefs      JSONB NOT NULL DEFAULT '[]',    -- [{canonicalId, type, weight}]
  lastSummarizedMessageId UUID,                   -- so we never re-summarize what's already summarized
  updatedAt       TIMESTAMPTZ DEFAULT now()
);

-- REPLACED: user_memory becomes a small, typed key-value store
-- with explicit categories instead of free-form keys
CREATE TABLE user_memory (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  userId        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  category      TEXT NOT NULL,                    -- 'preference' | 'profile' | 'domain' | 'instruction'
  memoryKey     TEXT NOT NULL,                    -- 'language' | 'tone' | 'scope' | 'always_cite' ...
  memoryValue   TEXT NOT NULL,                    -- 'Arabic' | 'concise' | 'retail banking' | 'true'
  source        TEXT NOT NULL DEFAULT 'explicit', -- 'explicit' (user set) | 'promoted' (lifted from chat) | 'inferred'
  confidence    REAL NOT NULL DEFAULT 1.0,
  evidenceChatId UUID REFERENCES chats(id) ON DELETE SET NULL,  -- where this fact came from, if promoted
  updatedAt     TIMESTAMPTZ DEFAULT now(),
  UNIQUE (userId, category, memoryKey)
);
CREATE INDEX ix_user_memory_user_cat ON user_memory(userId, category);
```

Why each change matters:

- **`message_citations` removes the mislabeled JSON.** Citations now have rank,
  score, and direct FK to the message that cited them — you can query "show me
  every answer that cited Chapter 3 Article 5" with one SQL.
- **`chat_memory.summary` becomes a real summary**, and
  `lastSummarizedMessageId` lets the summarizer be incremental — only
  re-summarize new messages, never the whole history.
- **`chat_memory.entityRefs` stores only canonicalIds.** No duplication of
  Neo4j's entity table; just pointers with a weight (how often this chat
  mentioned them).
- **`user_memory.category`** gives you four well-defined buckets so prompt
  assembly knows which ones to inject (preference + instruction always; profile
  + domain only when relevant).
- **`user_memory.source` + `evidenceChatId`** makes promotion auditable: if a
  fact was lifted from a specific chat, you can trace it back. Banking
  compliance loves audit trails.

---

## 6. Memory pipeline (per-turn flow, pseudocode)

```python
async def handleChatTurn(userId, chatId, query, mode, k, provider):
    # ---- READ phase: assemble the prompt ----
    user = await loadUser(userId)
    userMem = await loadUserMemory(userId, categories=['preference','instruction'])
    chatMem = await loadChatMemory(chatId)                  # may be None for a new chat
    recentTurns = await loadMessages(chatId, limit=4, order='desc')  # last 4 turns verbatim
    chunks = await retrieveChunks(query, mode, k, user.clearance)

    prompt = assemblePrompt(
        system   = SYSTEM_PROMPT,
        userMem  = userMem,           # ≤80 tokens, top-3 by relevance to query
        chatMem  = chatMem.summary,   # ≤300 tokens
        history  = recentTurns,       # ≤600 tokens, oldest first
        context  = chunks,            # ≤1500 tokens, citation-ready
        question = query
    )

    # ---- WRITE-1: store user message, start streaming ----
    userMsg = await insertMessage(chatId, 'user', query)
    yield from streamLLM(prompt)
    assistantMsg = await insertMessage(chatId, 'assistant', accumulated)

    # ---- WRITE-2: provenance ----
    await insertMessageCitations(assistantMsg.id, chunks)

    # ---- WRITE-3: chat memory (async, doesn't block stream) ----
    asyncio.create_task(updateChatMemory(chatId, assistantMsg.id))

    # ---- WRITE-4: maybe promote to user memory (async) ----
    asyncio.create_task(maybePromote(userId, chatId, userMsg, assistantMsg))
```

### The summarizer (background, debounced)

```python
async def updateChatMemory(chatId, latestMessageId):
    mem = await loadChatMemory(chatId)
    newMessages = await loadMessagesSince(chatId, mem.lastSummarizedMessageId)

    # Only re-summarize once we have N new turns OR token threshold exceeded
    if len(newMessages) < 6 and tokenCount(newMessages) < 1000:
        return

    newSummary = await llmSummarize(
        previousSummary=mem.summary,
        newMessages=newMessages,
        maxTokens=300,
        prompt="""Update the running summary with the new exchanges.
                  Keep facts the user has *asked about*, *decisions* made, and
                  *constraints* stated. Drop pleasantries. Stay under 300 tokens."""
    )
    newEntityRefs = mergeEntityRefs(mem.entityRefs, extractEntities(newMessages))
    await upsertChatMemory(chatId, newSummary, newEntityRefs, latestMessageId)
```

### The promoter (background, conservative)

```python
async def maybePromote(userId, chatId, userMsg, assistantMsg):
    # Pattern 1: explicit preference statement
    if matchesPattern(userMsg.content, [
        r"always answer in (\w+)",
        r"my (role|division) is (.+)",
        r"prefer (concise|detailed) answers",
    ]):
        await upsertUserMemory(userId, 'preference', extracted_key, extracted_value,
                               source='inferred', evidenceChatId=chatId, confidence=0.7)

    # Pattern 2: recurring entity across N chats
    # (run as a periodic job, not per-turn)
    pass
```

---

## 7. How the big systems do it

A short, honest comparison (high level, since internal designs aren't public):

- **ChatGPT "Memory"** — a small set of user-level facts (~free-form sentences)
  surfaced as "Reference saved memories" with a maximum count (~50). Stored
  per-user, injected into the system prompt on every turn, editable from a
  settings panel. They explicitly do *not* push the full chat history forward
  between conversations — only the memories that were promoted.
- **ChatGPT conversation history** — the messages of one chat session are
  passed in until the context window fills; older messages are dropped or
  compressed. Cross-chat continuity exists ONLY through the memory bucket
  above.
- **Claude Projects** — a "project knowledge" bucket (your domain memory),
  separate from chats within the project. Each chat is independent context.
  No automatic cross-chat memory — by design, to keep behavior predictable for
  enterprise users.
- **Claude conversation memory** (when available) — similar to ChatGPT's:
  small, user-controllable, auditable, separate from chat history.

The pattern is the same everywhere: **two layers, not three.** A chat-scoped
working memory (summary of recent turns) and a user-scoped long memory (tiny,
explicit, editable). They are read on every turn, written by different actors,
and never overlap.

---

## 8. Should memory be per-chat, per-user, or hybrid?

**Hybrid, but with strict rules:**

| | per-chat | per-user |
|---|---|---|
| Who writes it | Background summarizer | User explicitly OR promoter (conservative) |
| What it contains | Compressed history of THIS thread | Stable preferences and stable role facts |
| When it's read | Every turn in the same chat | Every turn across all chats |
| Lifetime | Dies with the chat | Survives chat deletion |
| Editable by user? | No (auto-managed) | Yes (settings page) |
| Promoted to the other? | A pattern in `chat_memory` can be promoted to `user_memory`, never the reverse | Never demoted |

**Why hybrid wins for Gazelle specifically.** You're in banking compliance.
Cross-chat user memory must be limited and auditable (regulators care). Chat
memory is essential because compliance questions are often multi-turn
("what about Article 5 paragraph 2?" only makes sense if the model remembers
that we just discussed Article 5). The promotion path with `evidenceChatId`
gives you a defensible audit trail for anything that crosses chats.

---

## 9. Examples and edge cases

### Example A — multi-turn drilling in one chat
```
Turn 1: "ما هي متطلبات الترخيص في الفصل الأول؟"
        → retrieved 5 chunks from Chapter_1 → answer cites c0001, c0003
        → chat_memory.summary = "User asking about Chapter 1 licensing reqs"
        → chat_memory.entityRefs += [{License-licensing, weight:1}]

Turn 2: "وماذا عن الفقرة الثانية؟"  ("and the second paragraph?")
        → prompt now includes:
            - chat_memory.summary  (knows we're on Chapter 1 licensing)
            - last 4 turns         (sees Turn 1 verbatim)
            - retrieved chunks     (biased toward Chapter_1)
        → model can resolve "the second paragraph" correctly
```

Without chat memory + history injection, Turn 2 has no anchor and either fails
or hallucinates.

### Example B — user-scoped preference
```
First chat, day 1: User says "Please answer in Arabic from now on."
        → promoter matches "answer in (\w+)" → upserts user_memory:
            category='preference', key='language', value='Arabic',
            source='inferred', confidence=0.7
Second chat, day 5: User asks "What is KYC?"
        → prompt assembly pulls user_memory.preference.language=Arabic
        → injects "User preference: answer in Arabic" into system block
        → model answers in Arabic without re-asking
```

### Example C — conflicting memory
```
user_memory.preference.tone = "concise" (set 6 months ago, confidence 1.0)
chat_memory in current chat suggests user wants detailed responses

Rule: chat_memory always wins for the current chat; user_memory is the
default for new chats. Detected conflicts are NOT auto-resolved — they're
surfaced in the user's settings page with "Update your preference?"
```

### Example D — chat deletion
```
Delete chat X → cascade deletes messages, message_citations, chat_memory.
user_memory rows with evidenceChatId=X have evidenceChatId set NULL
(thanks to ON DELETE SET NULL) so the fact survives but loses its trail.
This is intentional: we don't erase a user's stated preferences when they
clean up a chat.
```

### Example E — sensitive data
```
User pastes an account number into a chat → it ends up in messages and
potentially chat_memory.summary if the summarizer keeps it.

Mitigation:
  - The summarizer prompt MUST include "redact account numbers, NIDs, and
    any 10+ digit numeric sequences before storing".
  - The promoter MUST never lift sensitive patterns into user_memory.
  - Run a periodic PII scanner over chat_memory.summary and quarantine hits.
```

---

## 10. Token budget (the part nobody plans for and everyone regrets)

For a typical 8K-context chat model, here's the budget I recommend:

| Layer | Max tokens | Rationale |
|---|---|---|
| System prompt | 250 | Immutable rules |
| User memory (top-k injected) | 80 | 3-5 short facts max |
| Chat summary | 300 | Rolling, dense |
| Last N turns verbatim | 600 | ~4 turns of 150 tokens each |
| Retrieved context (chunks) | 1500 | The grounding evidence |
| Question + scratch | 200 | |
| **Subtotal input** | **2930** | |
| **Reserved for completion** | **2000** | Streamed answer |
| **Headroom** | **3070** | Tokenizer drift, safety margin |

If the chat exceeds N turns, the summarizer absorbs older turns into the
summary and the verbatim window stays bounded. **The total prompt size never
grows with chat length** — that's the property you want for scalability.

---

## 11. Migration plan (from your current code to this)

A safe, ordered migration. Each step is independently shippable.

1. **Add `OLLAMA_CHAT_MODEL` to `.env`** (already done) so chat actually works.
2. **Stop misusing `chat_memory.extractedEntities`.** Add a migration that
   creates `message_citations` and a one-shot backfill job that extracts
   chunkIds from `chat_memory.extractedEntities` into `message_citations`. Then
   change `chatEventGen` to write citations to the new table.
3. **Wire memory READS into the prompt.** Modify `streamTokens` (or its
   prompt-build helper) to accept `userMem`, `chatMem`, and `recentTurns`.
   Build these inside `chatStream`. Start with last-4-turns only; no
   summarization yet. This already fixes the multi-turn problem.
4. **Replace `buildChatSummary`** with a real summarizer call. Fire it
   asynchronously after each turn but only when accumulated new tokens exceed
   the threshold. Update `chat_memory.summary` and
   `chat_memory.lastSummarizedMessageId`.
5. **Add the `category`/`source`/`evidenceChatId` columns to `user_memory`.**
   Backfill `category='preference'` and `source='explicit'` for existing rows.
6. **Build the promoter** as a background job that scans recent
   `chat_memory.summary` rows for stable patterns and upserts into
   `user_memory`. Conservative thresholds; require ≥3 chats of evidence before
   promoting.
7. **Add a settings UI** for the user to view and edit `user_memory` rows
   (compliance: every change is in `audit_logs`).
8. **Add PII redaction** in the summarizer and the promoter (regex first,
   later swap in a proper PII model).

Steps 1-3 alone get you out of the current broken state. Steps 4-8 are the
scalable design.

---

## 12. TL;DR

- Your suspicion is right that something is off, but **the symptom is
  inverted from what you thought.** It's not that the tables overlap — it's
  that they don't get read. Both `chat_memory` and `user_memory` are written
  and never consumed.
- Keep both tables, but **redefine their jobs**: `chat_memory` is a rolling
  LLM-written summary + entity refs for THIS chat; `user_memory` is a tiny
  typed key-value store of preferences and stable profile facts.
- Split citations into `message_citations`. That single change removes the
  current overlap and gives you per-message provenance.
- **Prompt assembly is the only place memory is read**, in a deterministic
  order with strict per-layer token budgets.
- Promote chat-scoped patterns into user-scoped memory conservatively, with an
  evidence pointer for audit. Never demote.
- Hybrid (chat + user), not isolated, not global. The wins for banking
  compliance: defensible audit trail, predictable token budget, multi-turn
  works, cross-chat preferences work, and nothing duplicates because each
  fact has exactly one home with a written rule for which home it goes to.
