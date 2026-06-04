import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatView from './components/ChatView';
import GraphExplorer from './components/GraphExplorer';
import PipelineView from './components/PipelineView';
import Login from './components/Login';
import { useChats } from './hooks/useChats';
import { useAuth } from './hooks/useAuth';

const VIEWS = { CHAT: 'chat', GRAPH: 'graph', PIPELINE: 'pipeline' };
const SIDEBAR_KEY = 'gazelle.sidebar.open';

export default function App() {
  const auth = useAuth();
  const [view, setView] = useState(VIEWS.CHAT);
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    const v = localStorage.getItem(SIDEBAR_KEY);
    return v === null ? true : v === '1';
  });
  const chatState = useChats(auth.token);

  useEffect(() => {
    localStorage.setItem(SIDEBAR_KEY, sidebarOpen ? '1' : '0');
  }, [sidebarOpen]);

  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'n') {
        e.preventDefault();
        chatState.createChat();
        setView(VIEWS.CHAT);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [chatState]);

  if (!auth.token || !auth.user) {
    return <Login onLogin={auth.login} />;
  }

  return (
    <div className="flex h-full bg-cream overflow-hidden">
      <Sidebar
        open={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        view={view}
        onViewChange={setView}
        chatState={chatState}
        user={auth.user}
        onLogout={auth.logout}
      />
      <main className="flex-1 flex flex-col min-w-0 bg-cream">
        {view === VIEWS.CHAT && <ChatView chatState={chatState} user={auth.user} />}
        {view === VIEWS.GRAPH && <GraphExplorer />}
        {view === VIEWS.PIPELINE && <PipelineView />}
      </main>
    </div>
  );
}
