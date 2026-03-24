import { useContext } from 'react';
import { MobileMenuContext } from './mobileMenuCtx';

export function useMobileMenu() {
  const ctx = useContext(MobileMenuContext);
  if (!ctx) throw new Error('useMobileMenu must be used within MobileMenuProvider');
  return ctx;
}
