export type ChatThemeMode = "dark" | "light";

export type ChatUiSettings = {
  botName: string;
  brandColor: string;
  brandColorSecondary: string;
  logoUrl: string | null;
  avatarUrl: string | null;
  tagline: string | null;
  welcomeMessage: string;
  inputPlaceholder: string;
  markdownEnabled: boolean;
  citationsEnabled: boolean;
  confidenceEnabled: boolean;
  handoffEnabled: boolean;
  handoffMessage: string | null;
};

export const defaultChatUiSettings: ChatUiSettings = {
  botName: process.env.NEXT_PUBLIC_CHATBOT_NAME ?? "Atlas",
  brandColor: process.env.NEXT_PUBLIC_CHATBOT_BRAND_COLOR ?? "#0ea5e9",
  brandColorSecondary: process.env.NEXT_PUBLIC_CHATBOT_BRAND_COLOR_SECONDARY ?? "#0369a1",
  logoUrl: process.env.NEXT_PUBLIC_CHATBOT_LOGO_URL ?? null,
  avatarUrl: process.env.NEXT_PUBLIC_CHATBOT_AVATAR_URL ?? null,
  tagline: process.env.NEXT_PUBLIC_CHATBOT_TAGLINE ?? "Grounded answers for your business knowledge",
  welcomeMessage:
    process.env.NEXT_PUBLIC_CHATBOT_WELCOME_MESSAGE ??
    "Ask grounded questions about your documents and website sources. I will answer only from the indexed knowledge base and include citations for every response.",
  inputPlaceholder:
    process.env.NEXT_PUBLIC_CHATBOT_PLACEHOLDER ??
    "Ask a business question grounded in your knowledge base...",
  markdownEnabled: true,
  citationsEnabled: true,
  confidenceEnabled: true,
  handoffEnabled: true,
  handoffMessage: "A human teammate can take over if needed.",
};

export const CHAT_THEME_STORAGE_KEY = "rag_chat_theme_mode";

export function getInitialThemeMode(): ChatThemeMode {
  if (typeof window === "undefined") {
    return "dark";
  }
  const stored = window.localStorage.getItem(CHAT_THEME_STORAGE_KEY);
  if (stored === "dark" || stored === "light") {
    return stored;
  }
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}
