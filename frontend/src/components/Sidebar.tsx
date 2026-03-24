import { useState, useEffect } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  MessageSquare, StickyNote, CalendarDays, Settings, Plus,
  Trash2, LogOut, Sun, Moon, X, Bot
} from 'lucide-react';
import { api } from '../services/api';
import { useMobileMenu } from '../contexts/useMobileMenu';

interface SidebarProps {
  dark: boolean;
  toggleTheme: () => void;
  onLogout: () => void;
  onSelectConversation: (id: number) => void;
  onNewConversation: () => void;
  currentConversationId: number | null;
}

const navItems = [
  { to: '/', icon: MessageSquare, label: 'Chat' },
  { to: '/notes', icon: StickyNote, label: 'Notes' },
  { to: '/calendar', icon: CalendarDays, label: 'Calendar' },
  { to: '/settings', icon: Settings, label: 'Settings' },
];

export function Sidebar({ dark, toggleTheme, onLogout, onSelectConversation, onNewConversation, currentConversationId }: SidebarProps) {
  const [conversations, setConversations] = useState<{ id: number; title: string }[]>([]);
  const { open: mobileOpen, closeMenu } = useMobileMenu();
  const navigate = useNavigate();

  useEffect(() => {
    api.getConversations().then(setConversations).catch(() => {});
  }, [currentConversationId]);

  const handleDelete = async (e: React.MouseEvent, id: number) => {
    e.stopPropagation();
    await api.deleteConversation(id);
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (currentConversationId === id) onNewConversation();
  };

  const sidebar = (
    <div className="flex flex-col h-full bg-[var(--color-surface)] border-r border-[var(--color-border)]">
      <div className="p-4 flex items-center gap-2 border-b border-[var(--color-border)]">
        <Bot className="w-7 h-7 text-[var(--color-primary)]" />
        <span className="text-lg font-bold tracking-tight">DemoAssistant</span>
        <button onClick={closeMenu} className="ml-auto md:hidden p-1 rounded-lg hover:bg-[var(--color-surface-hover)]">
          <X className="w-5 h-5" />
        </button>
      </div>

      <nav className="p-2 space-y-1">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            onClick={closeMenu}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-[var(--color-primary)] text-white'
                  : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text)]'
              }`
            }
          >
            <Icon className="w-4.5 h-4.5" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="flex-1 overflow-y-auto px-2 py-2 border-t border-[var(--color-border)]">
        <div className="flex items-center justify-between px-3 py-2">
          <span className="text-xs font-semibold text-[var(--color-text-secondary)] uppercase tracking-wider">Chats</span>
          <button
            onClick={() => { onNewConversation(); navigate('/'); closeMenu(); }}
            className="p-1 rounded-md hover:bg-[var(--color-surface-hover)] text-[var(--color-text-secondary)]"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>
        {conversations.length === 0 ? (
          <p className="px-3 py-4 text-xs text-[var(--color-text-secondary)] text-center">
            No conversations yet
          </p>
        ) : (
          conversations.map((c) => (
            <button
              key={c.id}
              onClick={() => { onSelectConversation(c.id); navigate('/'); closeMenu(); }}
              className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-left group transition-colors ${
                currentConversationId === c.id
                  ? 'bg-[var(--color-surface-hover)] text-[var(--color-text)]'
                  : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]'
              }`}
            >
              <span className="truncate flex-1">{c.title}</span>
              <Trash2
                className="w-3.5 h-3.5 opacity-60 md:opacity-0 md:group-hover:opacity-60 hover:!opacity-100 shrink-0"
                onClick={(e) => handleDelete(e, c.id)}
              />
            </button>
          ))
        )}
      </div>

      <div className="p-2 border-t border-[var(--color-border)] space-y-1">
        <button onClick={toggleTheme} className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)]">
          {dark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
          {dark ? 'Light Mode' : 'Dark Mode'}
        </button>
        <button onClick={onLogout} className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-red-400 hover:bg-red-500/10">
          <LogOut className="w-4 h-4" />
          Sign Out
        </button>
      </div>
    </div>
  );

  return (
    <>
      {/* Mobile overlay with slide-in drawer */}
      <div
        className={`fixed inset-0 z-40 md:hidden transition-opacity duration-200 ${mobileOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'} bg-black/50`}
        onClick={closeMenu}
        aria-hidden={!mobileOpen}
      >
        <div
          className={`w-72 h-full bg-[var(--color-surface)] shadow-xl transition-transform duration-200 ease-out ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}`}
          onClick={(e) => e.stopPropagation()}
        >
          {sidebar}
        </div>
      </div>

      {/* Desktop sidebar */}
      <div className="hidden md:block w-64 h-screen shrink-0">
        {sidebar}
      </div>
    </>
  );
}
