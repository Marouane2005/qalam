"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useApp } from "@/components/Providers";
import { api, ApiError } from "@/lib/api";
import type { Answer, DocumentItem, DocumentText, Summary, Translation } from "@/lib/types";

type Tab = "summary" | "translation" | "ask";

const TARGETS = ["ar", "fr", "en"] as const;

export default function DocumentPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const router = useRouter();
  const { apiKey, label, locale } = useApp();
  const [document, setDocument] = useState<DocumentItem | null>(null);
  const [text, setText] = useState<DocumentText | null>(null);
  const [history, setHistory] = useState<Answer[]>([]);
  const [tab, setTab] = useState<Tab>("summary");
  const [error, setError] = useState("");
  const [target, setTarget] = useState<(typeof TARGETS)[number]>("fr");
  const [translation, setTranslation] = useState<Translation | null>(null);
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [translating, setTranslating] = useState(false);
  const [busySummary, setBusySummary] = useState(false);

  const refresh = useCallback(async () => {
    const [nextDocument, nextText, nextHistory] = await Promise.all([
      api<DocumentItem>(`/v1/documents/${id}`, apiKey),
      api<DocumentText>(`/v1/documents/${id}/text`, apiKey),
      api<Answer[]>(`/v1/documents/${id}/questions`, apiKey),
    ]);
    setDocument(nextDocument);
    setText(nextText);
    setHistory(nextHistory);
  }, [apiKey, id]);

  useEffect(() => {
    if (!apiKey || !id) return;
    let cancel = false;
    refresh().catch((caught: unknown) => {
      if (cancel) return;
      setError(caught instanceof ApiError ? caught.message : label("error"));
    });
    return () => {
      cancel = true;
    };
  }, [apiKey, id, label, refresh]);

  useEffect(() => {
    if (!document || (document.status !== "queued" && document.status !== "processing")) return;
    const timer = window.setInterval(() => {
      refresh().catch(() => undefined);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [document, refresh]);

  async function regenerate() {
    setBusySummary(true);
    setError("");
    try {
      const summary = await api<Summary>(`/v1/documents/${id}/summary`, apiKey, { method: "POST" });
      setDocument((current) =>
        current
          ? { ...current, summary_short: summary.short, summary_detailed: summary.detailed, summary_provider: summary.provider }
          : current,
      );
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : label("error"));
    } finally {
      setBusySummary(false);
    }
  }

  async function translate() {
    setTranslating(true);
    setError("");
    try {
      const result = await api<Translation>(`/v1/documents/${id}/translations`, apiKey, {
        method: "POST",
        body: JSON.stringify({ target_language: target }),
      });
      setTranslation(result);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : label("error"));
    } finally {
      setTranslating(false);
    }
  }

  async function ask(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = question.trim();
    if (!trimmed) return;
    setAsking(true);
    setError("");
    try {
      const answer = await api<Answer>("/v1/qa", apiKey, {
        method: "POST",
        body: JSON.stringify({ document_ids: [id], question: trimmed }),
      });
      setHistory((current) => [...current, answer]);
      setQuestion("");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : label("error"));
    } finally {
      setAsking(false);
    }
  }

  async function remove() {
    if (!window.confirm(label("confirmDelete"))) return;
    await api<void>(`/v1/documents/${id}`, apiKey, { method: "DELETE" });
    router.push("/");
  }

  async function reprocess() {
    setError("");
    const updated = await api<DocumentItem>(`/v1/documents/${id}/reprocess`, apiKey, { method: "POST" });
    setDocument(updated);
  }

  if (!document) {
    return (
      <main>
        <p className="text-moss">{error || label("loading")}</p>
      </main>
    );
  }

  const languageName =
    document.language === "ar" ? label("arabic") : document.language === "fr" ? label("french") : document.language === "en" ? label("english") : label("unknown");

  return (
    <main>
      <Link href="/" className="text-sm text-tide">
        {label("back")}
      </Link>
      <div className="mt-3 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 dir="auto" className="font-display text-4xl">
            {document.filename}
          </h1>
          <p className="mt-2 text-sm text-moss">
            {languageName} · {document.page_count} {label("pages")} ·{" "}
            {label(document.status === "processing" ? "statusReading" : document.status)} ·{" "}
            {new Date(document.created_at).toLocaleDateString(locale)}
          </p>
        </div>
        <div className="flex gap-3">
          {document.status === "failed" ? (
            <button type="button" onClick={() => void reprocess()} className="text-sm text-tide">
              {label("reprocess")}
            </button>
          ) : null}
          <button type="button" onClick={() => void remove()} className="text-sm text-seal">
            {label("delete")}
          </button>
        </div>
      </div>
      {document.status === "failed" && document.error ? (
        <p role="alert" className="mt-4 text-seal">
          {document.error}
        </p>
      ) : null}
      {(document.status === "queued" || document.status === "processing") && (
        <p role="status" className="mt-4 text-moss">
          {label("processing")}
        </p>
      )}
      {error ? (
        <p role="alert" className="mt-4 text-seal">
          {error}
        </p>
      ) : null}
      <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
        <section aria-label={label("text")} className="rounded-2xl border border-line bg-card p-5 shadow-sheet">
          {(text?.pages || []).map((page) => (
            <article key={page.page} id={`page-${page.page}`} className="border-b border-line/70 py-4 last:border-b-0">
              <p className="text-xs uppercase tracking-wide text-moss">
                {label("page")} {page.page}
              </p>
              <p dir="auto" className="mt-2 whitespace-pre-wrap leading-7">
                {page.text}
              </p>
            </article>
          ))}
          {!text?.pages.length ? <p className="text-moss">{label("noSummary")}</p> : null}
        </section>
        <section className="rounded-2xl border border-line bg-card p-5 shadow-sheet">
          <div className="flex gap-2" role="tablist">
            {(["summary", "translation", "ask"] as const).map((item) => (
              <button
                key={item}
                type="button"
                role="tab"
                aria-selected={tab === item}
                onClick={() => setTab(item)}
                className={`rounded-full px-3 py-1 text-sm ${tab === item ? "bg-ink text-card" : "bg-paper"}`}
              >
                {label(item)}
              </button>
            ))}
          </div>
          {tab === "summary" ? (
            <div className="mt-5" role="tabpanel">
              <h2 className="text-xs uppercase tracking-wide text-moss">{label("short")}</h2>
              <p dir="auto" className="mt-2 leading-7">
                {document.summary_short || label("noSummary")}
              </p>
              <h2 className="mt-5 text-xs uppercase tracking-wide text-moss">{label("detailed")}</h2>
              <p dir="auto" className="mt-2 leading-7">
                {document.summary_detailed || label("noSummary")}
              </p>
              <button
                type="button"
                onClick={() => void regenerate()}
                disabled={document.status !== "ready" || busySummary}
                className="mt-5 text-sm text-tide disabled:opacity-50"
              >
                {busySummary ? label("loading") : label("regenerate")}
              </button>
            </div>
          ) : null}
          {tab === "translation" ? (
            <div className="mt-5" role="tabpanel">
              <label htmlFor="target-language" className="text-sm">
                {label("target")}
              </label>
              <div className="mt-2 flex flex-wrap gap-2">
                <select
                  id="target-language"
                  value={target}
                  onChange={(event) => setTarget(event.target.value as (typeof TARGETS)[number])}
                  className="rounded-lg border border-line bg-paper px-3 py-2"
                >
                  {TARGETS.map((item) => (
                    <option key={item} value={item}>
                      {item === "ar" ? label("arabic") : item === "fr" ? label("french") : label("english")}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => void translate()}
                  disabled={document.status !== "ready" || translating}
                  className="rounded-full bg-tide px-4 py-2 text-sm text-card disabled:opacity-50"
                >
                  {translating ? label("translating") : label("translateAction")}
                </button>
              </div>
              {translation?.provider === "mock" ? <p className="mt-4 text-sm text-moss">{label("mockNote")}</p> : null}
              <div dir={translation?.direction || "auto"} className="mt-4 grid gap-4">
                {translation?.paragraphs.map((paragraph, index) => (
                  <p key={`${index}-${paragraph.slice(0, 24)}`} dir="auto" className="leading-7">
                    {paragraph}
                  </p>
                ))}
              </div>
            </div>
          ) : null}
          {tab === "ask" ? (
            <div className="mt-5" role="tabpanel">
              {history.length === 0 ? <p className="text-sm text-moss">{label("chatEmpty")}</p> : null}
              <ol className="grid gap-4">
                {history.map((item) => (
                  <li key={item.id} className="border-b border-line/80 pb-4">
                    <p className="text-sm text-moss" dir="auto">
                      {item.question}
                    </p>
                    <p dir="auto" className="mt-2 leading-7">
                      {item.answer}
                    </p>
                    {item.citations.length ? (
                      <ul className="mt-2 grid gap-2">
                        {item.citations.map((citation) => (
                          <li key={citation.chunk_id}>
                            <a href={`#page-${citation.page}`} className="text-sm text-tide">
                              {citation.filename} · {label("page")} {citation.page}
                            </a>
                            <blockquote dir="auto" className="mt-1 border-s-2 border-line ps-3 text-sm text-moss">
                              {citation.quote}
                            </blockquote>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </li>
                ))}
              </ol>
              <form onSubmit={(event) => void ask(event)} className="mt-4">
                <label htmlFor="question" className="sr-only">
                  {label("question")}
                </label>
                <textarea
                  id="question"
                  value={question}
                  onChange={(event) => setQuestion(event.target.value)}
                  placeholder={label("askPlaceholder")}
                  rows={3}
                  className="w-full rounded-lg border border-line bg-paper px-3 py-2"
                />
                <button
                  type="submit"
                  disabled={asking || document.status !== "ready" || question.trim().length === 0}
                  className="mt-3 rounded-full bg-ink px-4 py-2 text-sm text-card disabled:opacity-50"
                >
                  {asking ? label("loading") : label("send")}
                </button>
              </form>
            </div>
          ) : null}
        </section>
      </div>
    </main>
  );
}
