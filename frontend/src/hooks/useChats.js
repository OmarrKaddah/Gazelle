import { useState, useCallback } from 'react';

const STORAGE_KEY = 'gazelle.chats.v1';

function loadChats() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveChats(chats) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(chats));
}

export function useChats() {
  const [chats, setChats] = useState(loadChats);
  const [currentChatId, setCurrentChatId] = useState(() => loadChats()[0]?.id || null);

  const currentChat = chats.find((c) => c.id === currentChatId) || null;

  const createChat = useCallback(() => {
    const id = (crypto.randomUUID && crypto.randomUUID()) || `chat-${Date.now()}`;
    const chat = {
      id,
      title: 'New conversation',
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
    setChats((prev) => {
      const next = [chat, ...prev];
      saveChats(next);
      return next;
    });
    setCurrentChatId(id);
    return chat;
  }, []);

  const updateChat = useCallback((id, patch) => {
    setChats((prev) => {
      const next = prev.map((c) =>
        c.id === id ? { ...c, ...patch, updatedAt: Date.now() } : c
      );
      saveChats(next);
      return next;
    });
  }, []);

  const deleteChat = useCallback(
    (id) => {
      setChats((prev) => {
        const next = prev.filter((c) => c.id !== id);
        saveChats(next);
        return next;
      });
      setCurrentChatId((prev) => {
        if (prev === id) {
          const remaining = chats.filter((c) => c.id !== id);
          return remaining[0]?.id || null;
        }
        return prev;
      });
    },
    [chats]
  );

  const renameChat = useCallback((id, title) => {
    setChats((prev) => {
      const next = prev.map((c) => (c.id === id ? { ...c, title } : c));
      saveChats(next);
      return next;
    });
  }, []);

  return {
    chats,
    currentChat,
    currentChatId,
    setCurrentChatId,
    createChat,
    updateChat,
    deleteChat,
    renameChat,
  };
}
