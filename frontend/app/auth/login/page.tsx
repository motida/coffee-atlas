"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { AuthField, AuthFooterLink, AuthFormShell } from "@/components/auth/AuthForm";
import { useAuth } from "@/lib/auth-context";

export default function LoginPage() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login({ email, password });
      router.push("/account");
    } catch {
      setError("Invalid email or password.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthFormShell
      title="Log in"
      error={error}
      submitting={submitting}
      submitLabel="Log in"
      onSubmit={onSubmit}
      footer={<AuthFooterLink href="/auth/register" prompt="No account?" action="Register" />}
    >
      <AuthField
        label="Email"
        type="email"
        value={email}
        onChange={setEmail}
        required
        autoComplete="email"
      />
      <AuthField
        label="Password"
        type="password"
        value={password}
        onChange={setPassword}
        required
        autoComplete="current-password"
      />
    </AuthFormShell>
  );
}
