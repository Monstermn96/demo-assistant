import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './hooks/useAuth';
import { useChat } from './hooks/useChat';
import { useTheme } from './hooks/useTheme';
import { useSettings } from './hooks/useSettings';
import { MobileMenuProvider } from './contexts/MobileMenuContext';
import { Sidebar } from './components/Sidebar';
import { BottomTabs } from './components/BottomTabs';
import { Login } from './pages/Login';
import { Chat } from './pages/Chat';
import type { ChatStyle } from './pages/Chat';
import { Notes } from './pages/Notes';
import { Calendar } from './pages/Calendar';
import { Settings } from './pages/Settings';
import { Loader2 } from 'lucide-react';

function AuthenticatedApp() {
  const { logout } = useAuth();
  const { dark, toggle } = useTheme();
  const chat = useChat();
  const { settings, updateSettings, refreshTts } = useSettings();

  return (
    <BrowserRouter>
      <MobileMenuProvider>
      <div className="flex h-dvh overflow-hidden">
        <Sidebar
          dark={dark}
          toggleTheme={toggle}
          onLogout={logout}
          onSelectConversation={chat.loadConversation}
          onNewConversation={chat.newConversation}
          currentConversationId={chat.conversationId}
        />
        <main className="main-content-scroll flex-1 min-h-0 flex flex-col overflow-y-auto overflow-x-hidden pb-[calc(4.5rem+env(safe-area-inset-bottom,0px))] md:pb-6">
          <Routes>
            <Route path="/" element={
              <Chat
                messages={chat.messages}
                isStreaming={chat.isStreaming}
                onSend={chat.sendMessage}
                verbosity={settings.chat_verbosity as 'minimal' | 'standard' | 'detailed' | 'developer'}
                chatStyle={settings.chat_style as ChatStyle}
                ttsEnabled={settings.tts_enabled}
              />
            } />
            <Route path="/notes" element={<Notes />} />
            <Route path="/calendar" element={<Calendar />} />
            <Route path="/settings" element={
              <Settings
                currentModel={chat.model}
                onModelChange={chat.setModel}
                dark={dark}
                toggleTheme={toggle}
                appSettings={settings}
                onUpdateSettings={updateSettings}
                onRefreshTts={refreshTts}
              />
            } />
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </main>
        <BottomTabs />
      </div>
      </MobileMenuProvider>
    </BrowserRouter>
  );
}

export default function App() {
  const { isAuthenticated, loading, login, register, guestLogin } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-[var(--color-primary)]" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <BrowserRouter>
        <Routes>
          <Route path="*" element={<Login onLogin={login} onRegister={register} onGuestLogin={guestLogin} />} />
        </Routes>
      </BrowserRouter>
    );
  }

  return <AuthenticatedApp />;
}
