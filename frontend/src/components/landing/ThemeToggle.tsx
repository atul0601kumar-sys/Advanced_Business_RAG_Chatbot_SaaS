"use client";

import { useEffect, useState } from "react";

const storageKey = "abrag-theme";

export function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const root = document.documentElement;
    const initial = root.classList.contains("dark") ? "dark" : "light";
    setTheme(initial);
    setMounted(true);
  }, []);

  const toggleTheme = () => {
    const nextTheme = theme === "dark" ? "light" : "dark";
    document.documentElement.classList.toggle("dark", nextTheme === "dark");
    window.localStorage.setItem(storageKey, nextTheme);
    setTheme(nextTheme);
  };

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={mounted ? `Switch to ${theme === "dark" ? "light" : "dark"} mode` : "Toggle color mode"}
      className="button-secondary min-w-[8.25rem] text-[13px]"
    >
      <span className="mr-2 inline-flex h-2.5 w-2.5 rounded-full bg-[var(--accent)]" />
      {mounted ? (theme === "dark" ? "Light mode" : "Dark mode") : "Theme"}
    </button>
  );
}
