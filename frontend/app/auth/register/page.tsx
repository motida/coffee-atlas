"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { AuthField, AuthFooterLink, AuthFormShell } from "@/components/auth/AuthForm";
import { useAuth } from "@/lib/auth-context";

export default function RegisterPage() {
  const router = useRouter();
  const { register } = useAuth();
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setSubmitting(true);
    try {
      await register({ email, password, display_name: displayName || null });
      router.push("/account");
    } catch (err) {
      // fetchAPI throws "API error: 409 ..." on a taken email.
      setError(
        String(err).includes("409")
          ? "That email is already registered."
          : "Could not create your account. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthFormShell
      title="Create an account"
      error={error}
      submitting={submitting}
      submitLabel="Register"
      onSubmit={onSubmit}
      footer={<AuthFooterLink href="/auth/login" prompt="Already have an account?" action="Log in" />}
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
        label="Display name (optional)"
        type="text"
        value={displayName}
        onChange={setDisplayName}
        autoComplete="nickname"
      />
      <AuthField
        label="Password (min 8 characters)"
        type="password"
        value={password}
        onChange={setPassword}
        required
        minLength={8}
        autoComplete="new-password"
      />
    </AuthFormShell>
  );
}
