import { Menu } from 'lucide-react';
import { useMobileMenu } from '../contexts/useMobileMenu';

interface MobileHeaderProps {
  title: string;
  rightAction?: React.ReactNode;
}

export function MobileHeader({ title, rightAction }: MobileHeaderProps) {
  const { openMenu } = useMobileMenu();

  return (
    <header className="md:hidden sticky top-0 z-40 flex items-center justify-between gap-3 h-14 px-4 bg-[var(--color-surface)] border-b border-[var(--color-border)] shrink-0">
      <button
        type="button"
        onClick={openMenu}
        className="p-2 -ml-2 rounded-lg hover:bg-[var(--color-surface-hover)] text-[var(--color-text)] transition-colors active:scale-[0.98]"
        aria-label="Open menu"
      >
        <Menu className="w-5 h-5" />
      </button>
      <h1 className="flex-1 text-center text-lg font-bold truncate">
        {title}
      </h1>
      <div className="flex items-center justify-end min-w-[40px]">
        {rightAction ?? <span className="w-9" />}
      </div>
    </header>
  );
}
