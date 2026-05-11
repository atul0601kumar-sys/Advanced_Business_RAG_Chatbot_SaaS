import type { Metadata } from "next";
import { ToastProvider } from "@/components/toast-provider";
import "./globals.css";

const appName =
  process.env.NEXT_PUBLIC_APP_NAME ?? "Advanced Business RAG Chatbot SaaS";

export const metadata: Metadata = {
  title: appName,
  description:
    "Production-grade AI RAG chatbot platform for business knowledge, customer conversations, and grounded answers.",
};

const themeBootScript = `
(() => {
  const storageKey = "abrag-theme";
  const root = document.documentElement;
  try {
    const saved = window.localStorage.getItem(storageKey);
    const preferredDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    if ((saved ?? (preferredDark ? "dark" : "light")) === "dark") {
      root.classList.add("dark");
    } else {
      root.classList.remove("dark");
    }
  } catch {
    root.classList.remove("dark");
  }
})();
`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootScript }} />
      </head>
      <body>
        <ToastProvider>{children}</ToastProvider>
      </body>
    </html>
  );
}
