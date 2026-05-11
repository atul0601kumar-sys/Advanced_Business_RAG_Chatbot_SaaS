import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

const configDir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  esbuild: {
    jsx: "automatic",
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    include: ["./tests/**/*.test.ts", "./tests/**/*.test.tsx"],
    coverage: {
      reporter: ["text", "html", "json-summary"],
      include: [
        "src/components/auth-form.tsx",
        "src/components/chat/ChatInput.tsx",
        "src/components/chat/ChatWindow.tsx",
        "src/components/chat/CitationCard.tsx",
        "src/components/chat/MessageBubble.tsx",
        "src/components/dashboard/dashboard-home.tsx",
      ],
      thresholds: {
        lines: 80,
        statements: 80,
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(configDir, "./src"),
    },
  },
});
