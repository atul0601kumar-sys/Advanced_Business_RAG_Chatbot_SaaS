import { AuthForm } from "@/components/auth-form";

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,_rgba(37,99,235,0.22),_transparent_30%),linear-gradient(135deg,_#020617,_#111827,_#0f172a)] px-6 py-16">
      <AuthForm mode="login" />
    </main>
  );
}
