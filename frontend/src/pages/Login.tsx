import { useState } from 'react';
import { Bot, Loader2, Eye, EyeOff } from 'lucide-react';

interface LoginProps {
  onLogin: (username: string, password: string) => Promise<void>;
  onRegister: (username: string, password: string) => Promise<void>;
  onGuestLogin: () => Promise<void>;
}

export function Login({ onLogin, onRegister, onGuestLogin }: LoginProps) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [guestLoading, setGuestLoading] = useState(false);

  const validateRegistration = (): string | null => {
    if (!/^[a-zA-Z0-9_]{2,16}$/.test(username)) {
      return 'Username must be 2-16 characters: letters, numbers, underscores only';
    }
    if (password.length < 8) return 'Password must be at least 8 characters';
    if (!/[A-Z]/.test(password)) return 'Password needs at least one uppercase letter';
    if (!/[a-z]/.test(password)) return 'Password needs at least one lowercase letter';
    if (!/[0-9]/.test(password)) return 'Password needs at least one number';
    if (password !== confirmPassword) return 'Passwords do not match';
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (mode === 'register') {
      const validationError = validateRegistration();
      if (validationError) {
        setError(validationError);
        return;
      }
    }

    setLoading(true);
    try {
      if (mode === 'login') {
        await onLogin(username, password);
      } else {
        await onRegister(username, password);
      }
    } catch (err: any) {
      setError(err.message || (mode === 'login' ? 'Login failed' : 'Registration failed'));
    } finally {
      setLoading(false);
    }
  };

  const toggleMode = () => {
    setMode(m => m === 'login' ? 'register' : 'login');
    setError('');
    setConfirmPassword('');
  };

  const handleGuestLogin = async () => {
    setGuestLoading(true);
    setError('');
    try {
      await onGuestLogin();
    } catch (err: any) {
      setError(err.message || 'Guest login failed');
    } finally {
      setGuestLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)] px-4">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-[var(--color-primary)] flex items-center justify-center mb-4">
            <Bot className="w-9 h-9 text-white" />
          </div>
          <h1 className="text-2xl font-bold">DemoAssistant</h1>
          <p className="text-[var(--color-text-secondary)] text-sm mt-1">AI Assistant Demo</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-[var(--color-surface)] rounded-2xl border border-[var(--color-border)] p-6 space-y-4">
          <h2 className="text-lg font-semibold text-center">
            {mode === 'login' ? 'Sign In' : 'Create Account'}
          </h2>

          <div>
            <label className="block text-sm font-medium mb-1.5">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3 py-2.5 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50 focus:border-[var(--color-primary)]"
              required
              autoFocus
              autoComplete="username"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1.5">Password</label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3 py-2.5 pr-10 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50 focus:border-[var(--color-primary)]"
                required
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
                tabIndex={-1}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {mode === 'register' && (
            <>
              <div>
                <label className="block text-sm font-medium mb-1.5">Confirm Password</label>
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-lg bg-[var(--color-bg)] border border-[var(--color-border)] text-[var(--color-text)] focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]/50 focus:border-[var(--color-primary)]"
                  required
                  autoComplete="new-password"
                />
              </div>
              <ul className="text-xs text-[var(--color-text-secondary)] space-y-0.5 pl-4 list-disc">
                <li className={password.length >= 8 ? 'text-green-400' : ''}>At least 8 characters</li>
                <li className={/[A-Z]/.test(password) ? 'text-green-400' : ''}>One uppercase letter</li>
                <li className={/[a-z]/.test(password) ? 'text-green-400' : ''}>One lowercase letter</li>
                <li className={/[0-9]/.test(password) ? 'text-green-400' : ''}>One number</li>
              </ul>
            </>
          )}

          {error && (
            <p className="text-sm text-red-400 bg-red-500/10 rounded-lg px-3 py-2">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)] text-white font-medium transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loading && <Loader2 className="w-4 h-4 animate-spin" />}
            {mode === 'login' ? 'Sign In' : 'Create Account'}
          </button>

          <div className="relative flex items-center gap-3">
            <div className="flex-1 border-t border-[var(--color-border)]" />
            <span className="text-xs text-[var(--color-text-secondary)]">or</span>
            <div className="flex-1 border-t border-[var(--color-border)]" />
          </div>

          <button
            type="button"
            onClick={handleGuestLogin}
            disabled={guestLoading || loading}
            className="w-full py-2.5 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] hover:bg-[var(--color-surface-hover)] text-[var(--color-text)] font-medium transition-colors disabled:opacity-50 flex items-center justify-center gap-2 text-sm"
          >
            {guestLoading && <Loader2 className="w-4 h-4 animate-spin" />}
            Continue as Guest
          </button>

          <p className="text-sm text-center text-[var(--color-text-secondary)]">
            {mode === 'login' ? "Don't have an account?" : 'Already have an account?'}{' '}
            <button
              type="button"
              onClick={toggleMode}
              className="text-[var(--color-primary)] hover:underline font-medium"
            >
              {mode === 'login' ? 'Create one' : 'Sign in'}
            </button>
          </p>
        </form>
      </div>
    </div>
  );
}
