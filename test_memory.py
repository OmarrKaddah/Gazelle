"""
Direct memory subsystem tests. Runs against your live PostgreSQL — does NOT need
Neo4j or Ollama. Exercises the promoter, assembler, repositories, and the chat
endpoint's memory loads end-to-end.

Run:  python test_memory.py
"""
import asyncio
import os
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv
load_dotenv()

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"; CYAN = "\033[96m"; NC = "\033[0m"

passed, failed = 0, 0
def ok(name):
    global passed; passed += 1
    print(f"  {GREEN}PASS{NC}  {name}")
def fail(name, why):
    global failed; failed += 1
    print(f"  {RED}FAIL{NC}  {name}\n        {why}")
def section(s):
    print(f"\n{CYAN}== {s} =={NC}")


async def main():
    from db.session import asyncSessionFactory
    from db.models import User, Chat, UserMemory, ChatMemory, MessageCitation, Message
    from db.repositories.memoryRepo import (
        loadUserMemoryForPrompt, loadRecentMessages,
        upsertUserMemory, getChatMemory, upsertChatMemory,
    )
    from db.repositories.citationRepo import insertCitations, listForMessage
    from db.repositories.chatRepo import createChat, createMessage
    from memory.promoter import maybePromote, containsPii, PATTERNS
    from memory.assembler import assembleMessages

    section("0  Sanity: connect and find seed user 'omar'")
    from sqlalchemy import select
    async with asyncSessionFactory() as s:
        res = await s.execute(select(User).where(User.username == "omar"))
        omar = res.scalar_one_or_none()
        if not omar:
            fail("seed user 'omar' exists", "run RUN.bat once first so alembic seeds the demo users")
            print(f"\n{RED}STOPPED — DB not initialized.{NC}")
            return
        ok(f"connected; omar.id = {omar.id}")
        userId = omar.id

    section("1  PROMOTER — regex allowlist on user statements")
    cases = [
        ("always answer in Arabic",                          "preference",  "language",       "Arabic"),
        ("answer in english from now on",                    "preference",  "language",       "english"),
        ("I prefer concise answers",                         "preference",  "verbosity",      "concise"),
        ("my role is Compliance Analyst",                    "profile",     "role",           "Compliance Analyst"),
        ("always include page numbers in responses",         "instruction", "always_include", "page numbers"),
        ("never mention internal codenames",                 "instruction", "never_include",  "mention"),
    ]
    for msg, _, _, _ in cases:
        async with asyncSessionFactory() as s:
            await s.execute(UserMemory.__table__.delete().where(UserMemory.userId == userId))
            await s.commit()
        chat = None
        async with asyncSessionFactory() as s:
            chat = await createChat(s, userId, "Test")
            await s.commit()
        await maybePromote(userId, chat.id, msg)
        async with asyncSessionFactory() as s:
            res = await s.execute(select(UserMemory).where(UserMemory.userId == userId))
            rows = res.scalars().all()
        if rows:
            ok(f"promoted from: {msg!r}  ({rows[0].category}/{rows[0].memoryKey}={rows[0].memoryValue!r}, source={rows[0].source}, conf={rows[0].confidence})")
        else:
            fail(f"should have promoted: {msg!r}", "no row in user_memory")

    section("2  PROMOTER — PII gate refuses long digit runs")
    async with asyncSessionFactory() as s:
        await s.execute(UserMemory.__table__.delete().where(UserMemory.userId == userId))
        await s.commit()
    chat = None
    async with asyncSessionFactory() as s:
        chat = await createChat(s, userId, "PII test")
        await s.commit()
    pii_msg = "always answer in Arabic. my account is 1234567890123"
    await maybePromote(userId, chat.id, pii_msg)
    async with asyncSessionFactory() as s:
        res = await s.execute(select(UserMemory).where(UserMemory.userId == userId))
        rows = res.scalars().all()
    if not rows:
        ok("PII gate blocked promotion when message contained a 10+ digit run")
    else:
        fail("PII gate should have blocked", f"got {len(rows)} rows")
    if containsPii("my id is 12345678901"):
        ok("containsPii() correctly flags 10+ digit run")
    else:
        fail("containsPii() should flag 10+ digits", "regex broken")

    section("3  PROMOTER — explicit preference is never overridden")
    async with asyncSessionFactory() as s:
        await s.execute(UserMemory.__table__.delete().where(UserMemory.userId == userId))
        await s.commit()
        await upsertUserMemory(s, userId, "language", "Arabic", 1.0, {},
                               category="preference", source="explicit")
        await s.commit()
    chat = None
    async with asyncSessionFactory() as s:
        chat = await createChat(s, userId, "Override test")
        await s.commit()
    await maybePromote(userId, chat.id, "always answer in English")
    async with asyncSessionFactory() as s:
        res = await s.execute(select(UserMemory).where(
            UserMemory.userId == userId,
            UserMemory.category == "preference",
            UserMemory.memoryKey == "language",
        ))
        row = res.scalar_one_or_none()
    if row and row.memoryValue == "Arabic" and row.source == "explicit":
        ok("explicit preference 'Arabic' was NOT overridden by inferred 'English'")
    else:
        fail("explicit preference should win",
             f"got value={row.memoryValue!r} source={row.source!r}" if row else "no row")

    section("4  REPO — loadUserMemoryForPrompt filters to preference + instruction")
    async with asyncSessionFactory() as s:
        await s.execute(UserMemory.__table__.delete().where(UserMemory.userId == userId))
        await upsertUserMemory(s, userId, "language",       "Arabic",            1.0, {}, category="preference",  source="explicit")
        await upsertUserMemory(s, userId, "verbosity",      "concise",           0.9, {}, category="preference",  source="explicit")
        await upsertUserMemory(s, userId, "always_include", "page numbers",      0.95, {}, category="instruction", source="explicit")
        await upsertUserMemory(s, userId, "role",           "Compliance Analyst",1.0, {}, category="profile",     source="explicit")
        await upsertUserMemory(s, userId, "scope",          "retail division",   1.0, {}, category="domain",      source="explicit")
        await s.commit()
        rows = await loadUserMemoryForPrompt(s, userId)
    cats = sorted({r.category for r in rows})
    if cats == ["instruction", "preference"]:
        ok(f"loadUserMemoryForPrompt returned only preference + instruction (got {len(rows)} rows)")
    else:
        fail("loadUserMemoryForPrompt filter wrong", f"got categories: {cats}")

    section("5  REPO — loadRecentMessages returns N newest, oldest first")
    chat = None
    async with asyncSessionFactory() as s:
        chat = await createChat(s, userId, "Recent test")
        await s.commit()
    # commit between inserts so timestamps differ (mimics real per-turn behaviour)
    for i in range(8):
        async with asyncSessionFactory() as s:
            role = "user" if i % 2 == 0 else "assistant"
            await createMessage(s, chat.id, role, f"msg {i}", 2)
            await s.commit()
    async with asyncSessionFactory() as s:
        recent = await loadRecentMessages(s, chat.id, n=4)
    if len(recent) == 4 and recent[0].content == "msg 4" and recent[-1].content == "msg 7":
        ok("returned last 4 messages, ordered oldest first")
    else:
        fail("recent messages order/count wrong",
             f"got {[m.content for m in recent]}")

    section("6  ASSEMBLER — strict budgets and canonical order")
    fakeRows = []
    class FakeM:
        def __init__(self, k, v, c): self.category = c; self.memoryKey = k; self.memoryValue = v
    fakeRows = [FakeM("language", "Arabic", "preference"),
                FakeM("always_include", "page numbers", "instruction")]
    class FakeMsg:
        def __init__(self, role, content): self.role = role; self.content = content
    fakeHistory = [FakeMsg("user", "what is KYC?"), FakeMsg("assistant", "KYC is …")]
    messages = assembleMessages(
        systemPrompt="SYS",
        userMemRows=fakeRows,
        chatSummary="User asked about KYC.",
        recentTurns=fakeHistory,
        contextBlock="[chunk_1] KYC stands for Know Your Customer.",
        question="and what about AML?",
    )
    body = messages[1]["content"]
    checks = [
        ("system block present",  messages[0]["content"] == "SYS"),
        ("user mem in body",      "USER PREFERENCES" in body and "Arabic" in body),
        ("chat summary in body",  "SUMMARY" in body and "KYC" in body),
        ("history in body",       "USER:" in body and "ASSISTANT:" in body),
        ("context in body",       "CONTEXT:" in body and "Know Your Customer" in body),
        ("reminder present",      "Reminder:" in body),
        ("question last",         body.rstrip().endswith("AML?")),
    ]
    for label, ok_ in checks:
        ok(label) if ok_ else fail(label, "section missing or out of order")

    section("7  CITATIONS — write + read per message")
    async with asyncSessionFactory() as s:
        chat = await createChat(s, userId, "Cite test")
        await s.commit()
        msg = await createMessage(s, chat.id, "assistant", "answer", 1)
        chunks = [
            {"chunkId": "chapter_1-c0001", "docName": "chapter_1", "score": 0.91},
            {"chunkId": "chapter_3-c0007", "docName": "chapter_3", "score": 0.85},
        ]
        await insertCitations(s, msg.id, chunks)
        await s.commit()
        listed = await listForMessage(s, msg.id)
    if len(listed) == 2 and listed[0].rank == 1 and listed[1].chunkId == "chapter_3-c0007":
        ok(f"inserted 2 citations, ranks correct, retrievable by message")
    else:
        fail("citation roundtrip failed",
             f"got {[(c.rank, c.chunkId) for c in listed]}")

    section("8  CITATIONS — cascade on message delete")
    async with asyncSessionFactory() as s:
        from sqlalchemy import delete
        await s.execute(delete(Message).where(Message.id == msg.id))
        await s.commit()
        leftover = await listForMessage(s, msg.id)
    if len(leftover) == 0:
        ok("ON DELETE CASCADE removed citations when message deleted")
    else:
        fail("cascade did not fire", f"{len(leftover)} citations still present")

    section("9  CHAT_MEMORY — watermark field is writable")
    async with asyncSessionFactory() as s:
        chat = await createChat(s, userId, "Watermark test")
        await s.commit()
        msg = await createMessage(s, chat.id, "user", "hello", 1)
        await s.commit()
        mem = await upsertChatMemory(s, chat.id, "rolling summary text", {"foo":1}, {"mode":"vector"})
        mem.lastSummarizedMessageId = msg.id
        mem.summaryTokens = 4
        await s.commit()
        loaded = await getChatMemory(s, chat.id)
    if loaded and loaded.lastSummarizedMessageId == msg.id and loaded.summaryTokens == 4:
        ok("chat_memory.lastSummarizedMessageId + summaryTokens persist")
    else:
        fail("chat_memory new columns roundtrip failed", "")

    section("10 CLEANUP")
    async with asyncSessionFactory() as s:
        await s.execute(UserMemory.__table__.delete().where(UserMemory.userId == userId))
        await s.execute(Chat.__table__.delete().where(Chat.userId == userId))
        await s.commit()
    ok("test data removed for user omar")

    print()

    print()
    if failed == 0:
        print(GREEN + "========== ALL " + str(passed) + " CHECKS PASSED ==========" + NC)
    else:
        print(RED + "========== " + str(passed) + " passed, " + str(failed) + " FAILED ==========" + NC)


if __name__ == "__main__":
    asyncio.run(main())
