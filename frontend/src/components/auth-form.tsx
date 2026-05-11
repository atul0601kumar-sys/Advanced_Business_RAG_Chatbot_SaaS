"use client";

import { login, signup } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

type Mode = "login" | "signup";

type AuthFormProps = {
  mode: Mode;
};

export function AuthForm({ mode }: AuthFormProps) {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const isSignup = mode === "signup";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    try {
      if (isSignup) {
        await signup({
          full_name: fullName,
          workspace_name: workspaceName,
          email,
          password,
        });
      } else {
        await login({ email, password });
      }
      router.push("/dashboard");
      router.refresh();
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : "Authentication failed.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="w-full max-w-md rounded-3xl border border-white/10 bg-slate-950/80 p-8 shadow-2xl shadow-blue-950/20">
      <div className="space-y-2">
        <p className="text-sm uppercase tracking-[0.2em] text-blue-200/80">
          {isSignup ? "Create workspace" : "Welcome back"}
        </p>
        <h1 className="text-3xl font-semibold text-white">
          {isSignup ? "Start your account" : "Login to your dashboard"}
        </h1>
      </div>

      <form className="mt-8 space-y-4" onSubmit={handleSubmit}>
        {isSignup ? (
          <>
            <label className="block space-y-2">
              <span className="text-sm text-slate-300">Full name</span>
              <input
                className="w-full rounded-2xl border border-white/10 bg-slate-900 px-4 py-3 text-white outline-none ring-0 placeholder:text-slate-500"
                onChange={(event) => setFullName(event.target.value)}
                placeholder="Aarav Singh"
                required
                value={fullName}
              />
            </label>
            <label className="block space-y-2">
              <span className="text-sm text-slate-300">Workspace name</span>
              <input
                className="w-full rounded-2xl border border-white/10 bg-slate-900 px-4 py-3 text-white outline-none ring-0 placeholder:text-slate-500"
                onChange={(event) => setWorkspaceName(event.target.value)}
                placeholder="Acme Revenue Team"
                required
                value={workspaceName}
              />
            </label>
          </>
        ) : null}

        <label className="block space-y-2">
          <span className="text-sm text-slate-300">Email</span>
          <input
            className="w-full rounded-2xl border border-white/10 bg-slate-900 px-4 py-3 text-white outline-none ring-0 placeholder:text-slate-500"
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
            required
            type="email"
            value={email}
          />
        </label>

        <label className="block space-y-2">
          <span className="text-sm text-slate-300">Password</span>
          <input
            className="w-full rounded-2xl border border-white/10 bg-slate-900 px-4 py-3 text-white outline-none ring-0 placeholder:text-slate-500"
            onChange={(event) => setPassword(event.target.value)}
            placeholder="••••••••"
            required
            type="password"
            value={password}
          />
        </label>

        {error ? (
          <p className="rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-200">
            {error}
          </p>
        ) : null}

        <button
          className="w-full rounded-2xl bg-blue-500 px-4 py-3 text-sm font-semibold text-white transition hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={isSubmitting}
          type="submit"
        >
          {isSubmitting ? "Please wait..." : isSignup ? "Create account" : "Login"}
        </button>
      </form>

      <p className="mt-6 text-sm text-slate-400">
        {isSignup ? "Already have an account?" : "Need an account?"}{" "}
        <a href={isSignup ? "/login" : "/signup"}>
          {isSignup ? "Login" : "Sign up"}
        </a>
      </p>
    </div>
  );
}
