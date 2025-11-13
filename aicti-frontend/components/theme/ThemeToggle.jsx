'use client';

import { useTheme } from 'next-themes';
import { useEffect, useState } from 'react';

export default function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  if (!mounted) return null;

  const toggle = () => setTheme(theme === 'dark' ? 'light' : 'dark');

  return (
    <button
      onClick={toggle}
      className="btn-ghost"
      style={{ marginLeft: 12 }}
      aria-label="Toggle dark mode"
      type="button"
    >
      {theme === 'dark' ? 'Light' : 'Dark'}
    </button>
  );
}
