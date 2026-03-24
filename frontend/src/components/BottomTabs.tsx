import { NavLink } from 'react-router-dom';
import { MessageSquare, StickyNote, CalendarDays, Settings } from 'lucide-react';

const tabs = [
  { to: '/', icon: MessageSquare, label: 'Chat' },
  { to: '/notes', icon: StickyNote, label: 'Notes' },
  { to: '/calendar', icon: CalendarDays, label: 'Calendar' },
  { to: '/settings', icon: Settings, label: 'Settings' },
];

export function BottomTabs() {
  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 z-30 flex safe-bottom bg-[var(--color-surface)]/95 backdrop-blur-sm border-t border-[var(--color-border)] shadow-[0_-2px_10px_rgba(0,0,0,0.05)] dark:shadow-[0_-2px_10px_rgba(0,0,0,0.2)]">
      <div className="flex w-full pt-1.5 pb-2">
        {tabs.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex-1 flex flex-col items-center justify-center gap-0.5 min-h-[40px] py-1 text-[10px] transition-colors rounded-lg mx-px active:scale-[0.98] ${
                isActive ? 'text-[var(--color-primary)]' : 'text-[var(--color-text-secondary)]'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <span className="relative flex flex-col items-center justify-center">
                  {isActive && (
                    <span className="absolute -top-1.5 left-1/2 -translate-x-1/2 w-6 h-0.5 rounded-full bg-[var(--color-primary)]" aria-hidden />
                  )}
                  <Icon className="w-[18px] h-[18px]" />
                </span>
                <span className="leading-tight">{label}</span>
              </>
            )}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
