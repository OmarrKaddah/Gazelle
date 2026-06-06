from transformers import AutoTokenizer

from config import BGE_M3_PATH

tokenizer = AutoTokenizer.from_pretrained(BGE_M3_PATH)

BUDGET_USER_MEM = 80
BUDGET_CHAT_SUMM = 300
BUDGET_HISTORY = 600
BUDGET_CONTEXT = 20000
BUDGET_QUESTION = 500


def countTokens(text):
    return len(tokenizer.encode(text, add_special_tokens=False))


def truncateToBudget(text, budgetTokens):
    if not text:
        return ""
    tokens = tokenizer.encode(text, add_special_tokens=False)
    if len(tokens) <= budgetTokens:
        return text
    truncated = tokenizer.decode(tokens[:budgetTokens], skip_special_tokens=True)
    return truncated


def formatUserMemory(rows):
    if not rows:
        return ""
    lines = []
    for r in rows:
        lines.append(f"- [{r.category}] {r.memoryKey}: {r.memoryValue}")
    return "USER PREFERENCES & INSTRUCTIONS (apply to every answer):\n" + "\n".join(lines)


def formatChatSummary(summary):
    if not summary:
        return ""
    return f"SUMMARY OF EARLIER TURNS (recap, not new evidence):\n{summary}"


def formatHistory(recentTurns):

    if not recentTurns:
        return ""
    parts = ["RECENT TURNS (verbatim, oldest first):"]
    for m in recentTurns:
        role = "USER" if m.role == "user" else "ASSISTANT"
        parts.append(f"{role}: {m.content}")
    return "\n".join(parts)


def assembleMessages(systemPrompt, userMemRows, chatSummary, recentTurns, contextBlock, question):
    userMemText = truncateToBudget(formatUserMemory(userMemRows), BUDGET_USER_MEM)
    chatSummText = truncateToBudget(formatChatSummary(chatSummary), BUDGET_CHAT_SUMM)
    historyText = truncateToBudget(formatHistory(recentTurns), BUDGET_HISTORY)
    contextText = truncateToBudget(contextBlock, BUDGET_CONTEXT)
    questionText = truncateToBudget(question, BUDGET_QUESTION)
    

    sections = [systemPrompt]
    if userMemText:
        sections.append(userMemText)
    if chatSummText:
        sections.append(chatSummText)
    if historyText:
        sections.append(historyText)
    sections.append(f"CONTEXT:\n{contextText}")
    sections.append(
        "---\nReminder: answer ONLY using the CONTEXT above. Cite [chunkId] for every claim. "
        "If the context is insufficient, refuse using the exact refusal sentence per the system rules."
    )
    sections.append(f"QUESTION: {questionText}")

    return [
        {"role": "system", "content": systemPrompt},
        {"role": "user", "content": "\n\n".join(sections[1:])},
    ]
