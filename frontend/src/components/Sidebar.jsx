import React, { useState } from 'react';
import {
  LogoMark,
  PlusIcon,
  PanelLeftIcon,
  ChatIcon,
  GraphIcon,
  SettingsIcon,
  TrashIcon,
} from './Icons';

const TOOLS = [
  { id: 'chat', label: 'Chat', Icon: ChatIcon },
  { id: 'graph', label: 'Graph Explorer', Icon: GraphIcon },
  { id: 'pipeline', label: 'Pipeline', Icon: SettingsIcon },
];

export default function Sidebar({ open, onToggle, view, onViewChange, chatState, user, onLogout, isAdmin, onOpenAdmin }) {
  const { chats, currentChatId, setCurrentChatId, createChat, deleteChat } = chatState;

  const handleNewChat = () => {
    createChat();
    onViewChange('chat');
  };

  if (!open) {
    return (
      <aside className="w-14 bg-cream-frame border-r border-cream-border flex flex-col items-center py-3 gap-1 flex-shrink-0">
        <button
          onClick={onToggle}
          className="p-1 rounded-md hover:opacity-80 transition mb-1"
          title="Expand sidebar"
        >
          <LogoMark className="w-9 h-9" />
        </button>
        <button
          onClick={onToggle}
          className="p-2 rounded-md text-ink-muted hover:bg-cream-deeper hover:text-ink transition"
          title="Expand sidebar"
        >
          <PanelLeftIcon className="w-4 h-4" />
        </button>
        <div className="w-8 h-px bg-cream-border my-1" />
        <button
          onClick={handleNewChat}
          className="p-2 rounded-md text-ink-muted hover:bg-cream-deeper hover:text-ink transition"
          title="New chat"
        >
          <PlusIcon className="w-5 h-5" />
        </button>
        {TOOLS.map((t) => (
          <button
            key={t.id}
            onClick={() => onViewChange(t.id)}
            className={`p-2 rounded-md transition ${
              view === t.id
                ? 'bg-brand text-adib-glow'
                : 'text-ink-muted hover:bg-cream-deeper hover:text-ink'
            }`}
            title={t.label}
          >
            <t.Icon className="w-5 h-5" />
          </button>
        ))}
        {isAdmin && (
          <button
            onClick={onOpenAdmin}
            className="p-2 rounded-md text-ink-muted hover:bg-cream-deeper hover:text-ink transition"
            title="Admin Console"
          >
            <SettingsIcon className="w-5 h-5" />
          </button>
        )}
      </aside>
    );
  }

  return (
    <aside className="w-72 bg-cream-frame border-r border-cream-border flex flex-col flex-shrink-0">
      <div className="px-4 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <LogoMark className="w-9 h-9" />
          <div>
            <div className="font-serif text-[18px] leading-none text-brand tracking-tight">
              Gazelle
            </div>
            <div className="text-[10px] uppercase tracking-[0.16em] text-adib-deep mt-0.5">
              ADIB · Compliance
            </div>
          </div>
        </div>
        <button
          onClick={onToggle}
          className="p-1.5 rounded-md text-ink-muted hover:bg-cream-deeper hover:text-ink transition"
          title="Collapse sidebar"
        >
          <PanelLeftIcon className="w-4 h-4" />
        </button>
      </div>

      <div className="px-3">
        <button
          onClick={handleNewChat}
          className="w-full flex items-center gap-2.5 px-3 py-2 bg-cream-soft hover:bg-cream-deeper border border-cream-border hover:border-adib-soft rounded-lg text-[13px] font-medium text-ink transition group"
        >
          <PlusIcon className="w-4 h-4 text-adib" />
          <span>New chat</span>
          <kbd className="ml-auto text-[10px] text-ink-faint font-mono px-1.5 py-0.5 bg-cream-frame border border-cream-border rounded group-hover:border-cream-edge">
            ⌘N
          </kbd>
        </button>
      </div>

      <nav className="px-3 mt-5">
        <SectionLabel>Tools</SectionLabel>
        <div className="space-y-0.5 mt-1">
          {TOOLS.map((t) => (
            <NavItem
              key={t.id}
              Icon={t.Icon}
              label={t.label}
              active={view === t.id}
              onClick={() => onViewChange(t.id)}
            />
          ))}
          {isAdmin && (
            <NavItem
              Icon={SettingsIcon}
              label="Admin Console"
              active={false}
              onClick={onOpenAdmin}
            />
          )}
        </div>
      </nav>

      <div className="mt-5 flex-1 flex flex-col min-h-0">
        <div className="px-3">
          <SectionLabel>Recent</SectionLabel>
        </div>
        <div className="px-3 mt-1 flex-1 overflow-y-auto pb-2">
          {chats.length === 0 && (
            <div className="text-[12px] text-ink-faint px-3 py-2 italic">
              Conversations will appear here
            </div>
          )}
          <div className="space-y-0.5">
            {chats.map((c) => (
              <ChatItem
                key={c.id}
                chat={c}
                active={c.id === currentChatId && view === 'chat'}
                onSelect={() => {
                  setCurrentChatId(c.id);
                  onViewChange('chat');
                }}
                onDelete={() => deleteChat(c.id)}
              />
            ))}
          </div>
        </div>
      </div>

      <UserFooter user={user} onLogout={onLogout} />
    </aside>
  );
}

function SectionLabel({ children }) {
  return (
    <div className="text-[10px] uppercase tracking-[0.18em] text-ink-faint font-semibold px-3">
      {children}
    </div>
  );
}

function NavItem({ Icon, label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-[13px] transition ${
        active
          ? 'bg-brand text-white font-medium shadow-sm'
          : 'text-ink hover:bg-cream-deeper'
      }`}
    >
      <Icon className={`w-4 h-4 ${active ? 'text-adib-soft' : 'text-ink-muted'}`} />
      <span>{label}</span>
    </button>
  );
}

function ChatItem({ chat, active, onSelect, onDelete }) {
  const [hovered, setHovered] = useState(false);
  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className={`group relative rounded-md transition ${
        active ? 'bg-cream-soft border border-adib-soft shadow-sm' : 'border border-transparent hover:bg-cream-soft/60'
      }`}
    >
      <button
        onClick={onSelect}
        className="w-full text-left px-3 py-2 pr-8 text-[13px] text-ink truncate flex items-center"
        dir="auto"
      >
        <span className="truncate">{chat.title || 'New conversation'}</span>
      </button>
      {(hovered || active) && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          className="absolute right-1.5 top-1/2 -translate-y-1/2 p-1 rounded text-ink-faint hover:text-brand hover:bg-cream-deeper transition"
          title="Delete chat"
        >
          <TrashIcon className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  );
}

function UserFooter({ user, onLogout }) {
  const [open, setOpen] = useState(false);
  const initial = (user?.name || user?.username || '?').charAt(0).toUpperCase();
  const clearanceColor = {
    public: 'text-ink-muted',
    internal: 'text-adib-deep',
    confidential: 'text-gold-deep',
    restricted: 'text-red-700',
  }[user?.clearance] || 'text-ink-muted';

  return (
    <div className="border-t border-cream-border px-3 py-2.5 relative">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2.5 px-2 py-1.5 rounded-md hover:bg-cream-deeper transition group"
      >
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-brand to-adib-deep text-adib-glow flex items-center justify-center text-[13px] font-semibold ring-1 ring-adib/40">
          {initial}
        </div>
        <div className="flex-1 min-w-0 text-left">
          <div className="text-[13px] font-medium text-ink truncate leading-tight">
            {user?.name || user?.username}
          </div>
          <div className="text-[10px] text-ink-faint truncate flex items-center gap-1">
            <span>{user?.role}</span>
            <span>·</span>
            <span className={clearanceColor + ' font-medium uppercase tracking-wider'}>
              {user?.clearance}
            </span>
          </div>
        </div>
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
          <div className="absolute bottom-full left-3 right-3 mb-2 bg-cream-soft border border-cream-border rounded-lg shadow-lg z-20 overflow-hidden">
            <button
              onClick={() => {
                setOpen(false);
                onLogout?.();
              }}
              className="w-full px-3 py-2 text-left text-[13px] text-ink hover:bg-cream-deeper transition flex items-center gap-2"
            >
              <span>Sign out</span>
            </button>
          </div>
        </>
      )}
    </div>
  );
}
