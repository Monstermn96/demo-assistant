import { describe, it, expect } from 'vitest';

describe('App smoke test', () => {
  it('should pass a basic assertion', () => {
    expect(1 + 1).toBe(2);
  });

  it('should have access to DOM APIs via jsdom', () => {
    const div = document.createElement('div');
    div.textContent = 'ARIM';
    expect(div.textContent).toBe('ARIM');
  });
});
