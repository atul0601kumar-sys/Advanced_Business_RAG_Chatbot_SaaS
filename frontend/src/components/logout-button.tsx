"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { useToast } from "@/components/toast-provider";
import { logout } from "@/lib/auth";

export function LogoutButton() {
  const router = useRouter();
  const { pushToast } = useToast();
  const [isLoading, setIsLoading] = useState(false);

  async function handleLogout() {
    setIsLoading(true);
    try {
      await logout();
      router.push("/login");
      router.refresh();
    } catch (error) {
      pushToast({
        title: "Logout failed",
        description:
          error instanceof Error ? error.message : "The backend could not be reached.",
        tone: "error",
      });
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <button
      className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200 transition hover:bg-white/10"
      disabled={isLoading}
      onClick={handleLogout}
      type="button"
    >
      {isLoading ? "Logging out..." : "Logout"}
    </button>
  );
}
