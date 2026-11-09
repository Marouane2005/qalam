"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { useApp } from "@/components/Providers";
import { api, ApiError } from "@/lib/api";
import type { Locale, Me } from "@/lib/types";

const LOCALES: { id: Locale; label: string }[] = [
  { id: "en", label: "English" },
  { id: "fr", label: "Français" },
  { id: "ar", label: "العربية" },
];

function Mark() {
  return (
    <svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden="true">
      <rect width="32" height="32" rx="7" fill="#0f5e59" />
      <path
        d="M8 24c4.4-1.1 7.6-4.8 9.4-9.6 1.3 3.4 3.6 5.8 7.2 7.4"
        fill="none"
        stroke="#f6f1e8"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
      <circle cx="23" cy="9.5" r="1.5" fill="#f6f1e8" />
    </svg>
  );
}

function LanguageSwitcher() {
  const { locale, setLocale, label } = useApp();
  return (
    <div className="flex rounded-full border border-line bg-card p-0.5" role="group" aria-label={label("language")}>
      {LOCALES.map((item) => (
        <button
          key={item.id}
          type="button"
          lang={item.id}
          aria-pressed={locale === item.id}
          onClick={() => setLocale(item.id)}
          className={`rounded-full px-2.5 py-1 text-sm ${
            locale === item.id ? "bg-tide text-card" : "text-ink hover:bg-paper"
          }`}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

function KeyGate() {
  const { label, setApiKey } = useApp();
  const [value, setValue] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    const key = value.trim();
    if (!key) return;
    setBusy(true);
    setError("");
    try {
      await api<Me>("/v1/me", key);
      setApiKey(key);
    } catch (caught) {
      if (caught instanceof ApiError && caught.status === 401) setError(label("refused"));
      else if (caught instanceof ApiError && caught.status === 429) setError(label("rate"));
      else setError(label("error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-6 py-16">
      <div className="mb-8 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Mark />
          <div>
            <p className="font-display text-2xl leading-none">{label("pen")}</p>
            <p className="mt-1 text-sm text-moss">{label("tagline")}</p>
          </div>
        </div>
        <LanguageSwitcher />
      </div>
      <form onSubmit={submit} className="rounded-2xl border border-line bg-card p-6 shadow-sheet">
        <h1 className="font-display text-3xl">{label("keyTitle")}</h1>
        <p className="mt-3 text-sm leading-6 text-moss">{label("keyBody")}</p>
        <label className="mt-6 block text-sm font-medium" htmlFor="api-key">
          {label("keyLabel")}
        </label>
        <input
          id="api-key"
          name="api-key"
          type="password"
          autoComplete="off"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          className="mt-2 w-full rounded-lg border border-line bg-paper px-3 py-2"
        />
        <p className="mt-2 text-xs text-moss">{label("savedLocally")}</p>
        {error ? (
          <p role="alert" className="mt-3 text-sm text-seal">
            {error}
          </p>
        ) : null}
        <button
          type="submit"
          disabled={busy || value.trim().length === 0}
          className="mt-5 rounded-full bg-tide px-5 py-2 text-sm text-card disabled:opacity-50"
        >
          {busy ? label("checking") : label("continue")}
        </button>
      </form>
    </main>
  );
}

const LINKS = [
  { href: "/", key: "library" },
  { href: "/upload", key: "upload" },
  { href: "/extract", key: "extract" },
] as const;

export function Shell({ children }: { children: React.ReactNode }) {
  const { ready, apiKey, label, forgetKey, me } = useApp();
  const pathname = usePathname();
  if (!ready) {
    return <div className="min-h-screen" />;
  }
  if (!apiKey) return <KeyGate />;
  return (
    <div className="min-h-screen">
      <header className="border-b border-line/80 bg-paper/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-3 px-5 py-4">
          <Link href="/" className="flex items-center gap-3">
            <Mark />
            <span className="font-display text-2xl leading-none">{label("pen")}</span>
          </Link>
          <nav className="flex flex-wrap gap-1" aria-label={label("primaryNav")}>
            {LINKS.map((link) => {
              const active = link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  aria-current={active ? "page" : undefined}
                  className={`rounded-full px-3 py-1.5 text-sm ${
                    active ? "bg-ink text-card" : "text-ink hover:bg-card"
                  }`}
                >
                  {label(link.key)}
                </Link>
              );
            })}
          </nav>
          <div className="ms-auto flex flex-wrap items-center gap-3">
            {me ? (
              <p className="text-sm text-moss">
                <span className="sr-only">{label("workspace")}: </span>
                {me.workspace.name}
              </p>
            ) : null}
            <LanguageSwitcher />
            <button type="button" onClick={forgetKey} className="text-sm text-seal underline-offset-2 hover:underline">
              {label("forget")}
            </button>
          </div>
        </div>
      </header>
      <div className="mx-auto max-w-6xl px-5 py-8">{children}</div>
    </div>
  );
}
