import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatView from './components/ChatView';
import GraphExplorer from './components/GraphExplorer';
import PipelineView from './components/PipelineView';
import Login from './components/Login';
import AdminPage from './components/AdminPage';
import RequireRole from './components/RequireRole';
import { useChats } from './hooks/useChats';
import { useAuth } from './hooks/useAuth';
import { ROLES, isAdmin, defaultAreaForUser } from './lib/roles';

const VIEWS = { CHAT: 'chat', GRAPH: 'graph', PIPELINE: 'pipeline' };
const AREAS = { MAIN: 'main', ADMIN: 'admin' };
const SIDEBAR_KEY = 'gazelle.sidebar.open';

export default function App() {
  const auth = useAuth();
  const [view, setView] = useState(VIEWS.CHAT);
  const [area, setArea] = useState(AREAS.MAIN);
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

  if (area === AREAS.ADMIN) {
    return (
      <RequireRole user={auth.user} role={ROLES.ADMIN}>
        <AdminPage
          user={auth.user}
          onLogout={auth.logout}
          onEnterChat={() => setArea(AREAS.MAIN)}
        />
      </RequireRole>
    );
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
        isAdmin={isAdmin(auth.user)}
        onOpenAdmin={() => setArea(AREAS.ADMIN)}
      />
      <main className="flex-1 flex flex-col min-w-0 bg-cream">
        {view === VIEWS.CHAT && <ChatView chatState={chatState} user={auth.user} />}
        {view === VIEWS.GRAPH && <GraphExplorer />}
        {view === VIEWS.PIPELINE && <PipelineView />}
      </main>
    </div>
  );
}
