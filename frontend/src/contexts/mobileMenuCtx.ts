import { createContext } from 'react';

export interface MobileMenuContextValue {
  open: boolean;
  setOpen: (open: boolean) => void;
  openMenu: () => void;
  closeMenu: () => void;
}

export const MobileMenuContext = createContext<MobileMenuContextValue | null>(null);
