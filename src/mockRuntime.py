import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone


MOCK_USER_ID = uuid.UUID('11111111-1111-1111-1111-111111111111')
MOCK_SESSION_TOKEN = 'mock-runtime-token'


def nowUtc():
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class MockAuthUser:
    id: uuid.UUID = MOCK_USER_ID
    username: str = 'local-admin'
    role: str = 'admin'
    clearance: str = 'restricted'


@dataclass(slots=True)
class MockChat:
    id: uuid.UUID
    userId: uuid.UUID
    title: str
    createdAt: datetime
    updatedAt: datetime


@dataclass(slots=True)
class MockMessage:
    id: uuid.UUID
    chatId: uuid.UUID
    role: str
    content: str
    tokenCount: int
    createdAt: datetime


@dataclass(slots=True)
class MockChatMemory:
    id: uuid.UUID
    chatId: uuid.UUID
    summary: str
    extractedEntities: dict
    metadataJson: dict
    updatedAt: datetime


@dataclass(slots=True)
class MockUserMemory:
    id: uuid.UUID
    userId: uuid.UUID
    memoryKey: str
    memoryValue: str
    confidence: float
    metadataJson: dict
    updatedAt: datetime


@dataclass(slots=True)
class MockAuditLog:
    id: uuid.UUID
    userId: uuid.UUID | None
    action: str
    entityType: str
    entityId: str
    createdAt: datetime


@dataclass(slots=True)
class MockSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, excType, exc, tb):
        return False

    async def commit(self):
        return None

    async def flush(self):
        return None


mockAuthUser = MockAuthUser()
mockChats: dict[uuid.UUID, MockChat] = {}
mockMessages: dict[uuid.UUID, list[MockMessage]] = defaultdict(list)
mockChatMemory: dict[uuid.UUID, MockChatMemory] = {}
mockUserMemory: dict[tuple[uuid.UUID, str], MockUserMemory] = {}
mockAuditLogs: list[MockAuditLog] = []


def getMockUser():
    return {
        'id': str(mockAuthUser.id),
        'username': mockAuthUser.username,
        'name': 'Local Admin',
        'role': mockAuthUser.role,
        'clearance': mockAuthUser.clearance,
    }


def getMockUserByUsername(username: str):
    return mockAuthUser


def getMockUserByToken(tokenHash: str):
    return mockAuthUser


def createMockSession():
    return MockSession()


def issueMockToken():
    return MOCK_SESSION_TOKEN


def revokeMockToken(token: str):
    return None


def createMockChat(userId: uuid.UUID, title: str):
    row = MockChat(uuid.uuid4(), userId, title, nowUtc(), nowUtc())
    mockChats[row.id] = row
    return row


def listMockChats(userId: uuid.UUID, limit: int, offset: int):
    rows = [chat for chat in mockChats.values() if chat.userId == userId]
    rows.sort(key=lambda chat: chat.updatedAt, reverse=True)
    return rows[offset:offset + limit]


def getMockChatById(userId: uuid.UUID, chatId: uuid.UUID):
    row = mockChats.get(chatId)
    if not row or row.userId != userId:
        return None
    return row


def deleteMockChat(userId: uuid.UUID, chatId: uuid.UUID):
    row = getMockChatById(userId, chatId)
    if not row:
        return None
    del mockChats[chatId]
    mockMessages.pop(chatId, None)
    mockChatMemory.pop(chatId, None)
    return None


def createMockMessage(chatId: uuid.UUID, role: str, content: str, tokenCount: int):
    row = MockMessage(uuid.uuid4(), chatId, role, content, tokenCount, nowUtc())
    mockMessages[chatId].append(row)
    chat = mockChats.get(chatId)
    if chat:
        chat.updatedAt = nowUtc()
    return row


def listMockMessages(chatId: uuid.UUID, limit: int, offset: int):
    rows = mockMessages.get(chatId, [])
    return rows[offset:offset + limit]


def upsertMockChatMemory(chatId: uuid.UUID, summary: str, extractedEntities: dict, metadata: dict):
    row = mockChatMemory.get(chatId)
    if row:
        row.summary = summary
        row.extractedEntities = extractedEntities
        row.metadataJson = metadata
        row.updatedAt = nowUtc()
        return row
    row = MockChatMemory(uuid.uuid4(), chatId, summary, extractedEntities, metadata, nowUtc())
    mockChatMemory[chatId] = row
    return row


def getMockChatMemory(chatId: uuid.UUID):
    return mockChatMemory.get(chatId)


def listMockUserMemory(userId: uuid.UUID):
    rows = [row for (rowUserId, _), row in mockUserMemory.items() if rowUserId == userId]
    rows.sort(key=lambda row: row.updatedAt, reverse=True)
    return rows


def upsertMockUserMemory(userId: uuid.UUID, memoryKey: str, memoryValue: str, confidence: float, metadata: dict):
    key = (userId, memoryKey)
    row = mockUserMemory.get(key)
    if row:
        row.memoryValue = memoryValue
        row.confidence = confidence
        row.metadataJson = metadata
        row.updatedAt = nowUtc()
        return row
    row = MockUserMemory(uuid.uuid4(), userId, memoryKey, memoryValue, confidence, metadata, nowUtc())
    mockUserMemory[key] = row
    return row


def logMockAudit(userId, action: str, entityType: str, entityId: str):
    row = MockAuditLog(uuid.uuid4(), userId, action, entityType, entityId, nowUtc())
    mockAuditLogs.append(row)
    return row