import { useCallback, useEffect, useMemo, useState } from 'react';
import { authHeaders } from './useAuth';


export function useChats(authToken) {
  const [chats, setChats] = useState([]);
  const [currentChatId, setCurrentChatId] = useState(null);
  const [currentChat, setCurrentChat] = useState(null);

  const chatMap = useMemo(() => new Map(chats.map((c) => [c.id, c])), [chats]);

  const refreshChats = useCallback(async () => {
    if (!authToken) return;
    const res = await fetch('/api/chats?limit=100&offset=0', { headers: { ...authHeaders() } });
    const data = await res.json();
    const nextChats = data.chats || [];
    setChats(nextChats);
    if (!currentChatId && nextChats.length > 0) {
      setCurrentChatId(nextChats[0].id);
    }
  }, [authToken, currentChatId]);

  const refreshCurrentChat = useCallback(async () => {
    if (!authToken || !currentChatId) {
      setCurrentChat(null);
      return;
    }
    const res = await fetch(`/api/chats/${currentChatId}?limit=300&offset=0`, { headers: { ...authHeaders() } });
    if (!res.ok) {
      setCurrentChat(null);
      return;
    }
    const data = await res.json();
    const fresh = data.chat || null;
    setCurrentChat((prev) => {
      if (!fresh || !prev?.messages?.length) return fresh;
      return {
        ...fresh,
        messages: fresh.messages.map((msg, i) => ({
          ...msg,
          citations: prev.messages[i]?.citations ?? msg.citations,
          mode: prev.messages[i]?.mode ?? msg.mode,
        })),
      };
    });
  }, [authToken, currentChatId]);

  useEffect(() => {
    refreshChats();
  }, [refreshChats]);

  useEffect(() => {
    refreshCurrentChat();
  }, [refreshCurrentChat]);

  const createChat = useCallback(async () => {
    const res = await fetch('/api/chats', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ title: 'New conversation' }),
    });
    const data = await res.json();
    const chat = data.chat;
    setChats((prev) => [chat, ...prev]);
    setCurrentChatId(chat.id);
    setCurrentChat(chat);
    return chat;
  }, []);

  const updateChat = useCallback((id, patch) => {
    setCurrentChat((prev) => {
      if (!prev || prev.id !== id) return prev;
      return { ...prev, ...patch };
    });
    setChats((prev) => {
      const next = prev.map((c) => (c.id === id ? { ...c, ...patch } : c));
      return next;
    });
    if (patch.title !== undefined) {
      fetch(`/api/chats/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ title: patch.title }),
      });
    }
  }, []);

  const deleteChat = useCallback(
    async (id) => {
      await fetch(`/api/chats/${id}`, { method: 'DELETE', headers: { ...authHeaders() } });
      setChats((prev) => prev.filter((c) => c.id !== id));
      if (currentChatId === id) {
        const remaining = chats.filter((c) => c.id !== id);
        setCurrentChatId(remaining[0]?.id || null);
      }
    },
    [chats, currentChatId]
  );

  const renameChat = useCallback((id, title) => {
    updateChat(id, { title });
  }, [updateChat]);

  useEffect(() => {
    if (!currentChat && currentChatId && chatMap.has(currentChatId)) {
      setCurrentChat({ ...chatMap.get(currentChatId), messages: [] });
    }
  }, [currentChat, currentChatId, chatMap]);

  return {
    chats,
    currentChat,
    currentChatId,
    setCurrentChatId,
    createChat,
    updateChat,
    deleteChat,
    renameChat,
    refreshChats,
    refreshCurrentChat,
  };
}
