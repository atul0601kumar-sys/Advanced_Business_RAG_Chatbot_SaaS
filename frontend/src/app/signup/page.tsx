import { AuthForm } from "@/components/auth-form";

export default function SignupPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-[radial-gradient(circle_at_top,_rgba(14,165,233,0.18),_transparent_30%),linear-gradient(135deg,_#020617,_#0f172a,_#082f49)] px-6 py-16">
      <AuthForm mode="signup" />
    </main>
  );
}
