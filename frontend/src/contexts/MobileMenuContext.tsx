import { useState, useCallback, type ReactNode } from 'react';
import { MobileMenuContext } from './mobileMenuCtx';

export function MobileMenuProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const openMenu = useCallback(() => setOpen(true), []);
  const closeMenu = useCallback(() => setOpen(false), []);
  return (
    <MobileMenuContext.Provider value={{ open, setOpen, openMenu, closeMenu }}>
      {children}
    </MobileMenuContext.Provider>
  );
}
