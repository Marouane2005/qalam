"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useApp } from "@/components/Providers";
import { dateLocale } from "@/lib/i18n";
import { api } from "@/lib/api";
import type { DocumentItem, DocumentList } from "@/lib/types";

const FILTERS = ["all", "ar", "fr", "en"] as const;

function languageLabel(code: string | null, label: (key: "arabic" | "french" | "english" | "unknown") => string) {
  if (code === "ar") return label("arabic");
  if (code === "fr") return label("french");
  if (code === "en") return label("english");
  return label("unknown");
}

export default function LibraryPage() {
  const { apiKey, label, locale } = useApp();
  const [items, setItems] = useState<DocumentItem[] | null>(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("all");

  useEffect(() => {
    if (!apiKey) return;
    let cancel = false;
    api<DocumentList>("/v1/documents", apiKey)
      .then((body) => {
        if (!cancel) setItems(body.items);
      })
      .catch(() => {
        if (!cancel) setError(label("error"));
      });
    return () => {
      cancel = true;
    };
  }, [apiKey, label]);

  const visible = (items || []).filter((item) => filter === "all" || item.language === filter);

  return (
    <main>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-4xl">{label("library")}</h1>
          <p className="mt-2 max-w-xl text-moss">{label("tagline")}</p>
        </div>
        <Link href="/upload" className="rounded-full bg-tide px-4 py-2 text-sm text-card">
          {label("upload")}
        </Link>
      </div>
      <div className="mt-6 flex flex-wrap gap-2" role="group" aria-label={label("filter")}>
        {FILTERS.map((item) => (
          <button
            key={item}
            type="button"
            aria-pressed={filter === item}
            onClick={() => setFilter(item)}
            className={`rounded-full border px-3 py-1 text-sm ${
              filter === item ? "border-tide bg-tide text-card" : "border-line bg-card"
            }`}
          >
            {item === "all" ? label("all") : languageLabel(item, label)}
          </button>
        ))}
      </div>
      {error ? (
        <p role="alert" className="mt-6 text-seal">
          {error}
        </p>
      ) : null}
      {items === null ? <p className="mt-8 text-moss">{label("loading")}</p> : null}
      {items && visible.length === 0 ? (
        <div className="mt-10 rounded-2xl border border-dashed border-line bg-card/70 px-6 py-12">
          <h2 className="font-display text-2xl">{items.length === 0 ? label("emptyTitle") : label("nothingMatched")}</h2>
          <p className="mt-2 text-moss">{items.length === 0 ? label("emptyBody") : null}</p>
        </div>
      ) : null}
      <ul className="mt-6 grid gap-4">
        {visible.map((item) => (
          <li key={item.id}>
            <Link
              href={`/documents/${item.id}`}
              className="block rounded-2xl border border-line bg-card px-5 py-4 shadow-sheet transition hover:-translate-y-0.5"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-3">
                <h2 dir="auto" className="font-display text-2xl">
                  {item.filename}
                </h2>
                <p className="text-xs uppercase tracking-wide rtl:tracking-normal text-moss">
                  {languageLabel(item.language, label)} ·{" "}
                  {label(item.status === "processing" ? "statusReading" : item.status)}
                </p>
              </div>
              <p dir="auto" className="mt-2 line-clamp-2 text-sm leading-6 text-ink/80">
                {item.summary_short || item.error || " "}
              </p>
              <p className="mt-3 text-xs text-moss">
                {new Date(item.created_at).toLocaleDateString(dateLocale(locale))} · {item.page_count} {label("pages")}
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
