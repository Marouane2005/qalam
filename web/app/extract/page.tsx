"use client";

import { useEffect, useState } from "react";

import { useApp } from "@/components/Providers";
import { api, ApiError } from "@/lib/api";
import type { DocumentList, Extraction } from "@/lib/types";

const EXAMPLE = `{
  "type": "object",
  "required": ["invoice_number", "total"],
  "properties": {
    "invoice_number": { "type": "string" },
    "date": { "type": "string" },
    "seller": { "type": "string" },
    "buyer": { "type": "string" },
    "total": { "type": "string" },
    "currency": { "type": "string" }
  }
}`;

export default function ExtractPage() {
  const { apiKey, label } = useApp();
  const [documents, setDocuments] = useState<DocumentList["items"]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [schema, setSchema] = useState(EXAMPLE);
  const [result, setResult] = useState<Extraction | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!apiKey) return;
    let cancel = false;
    api<DocumentList>("/v1/documents?limit=100", apiKey)
      .then((body) => {
        if (!cancel) setDocuments(body.items.filter((item) => item.status === "ready"));
      })
      .catch(() => {
        if (!cancel) setError(label("error"));
      });
    return () => {
      cancel = true;
    };
  }, [apiKey, label]);

  function toggle(id: string) {
    setSelected((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  }

  async function run(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    setResult(null);
    if (selected.length === 0) {
      setError(label("chooseDocs"));
      return;
    }
    let parsed: unknown;
    try {
      parsed = JSON.parse(schema);
    } catch {
      setError(label("invalidJson"));
      return;
    }
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      setError(label("invalidJson"));
      return;
    }
    setBusy(true);
    try {
      const body = await api<Extraction>("/v1/extract", apiKey, {
        method: "POST",
        body: JSON.stringify({ document_ids: selected, schema: parsed }),
      });
      setResult(body);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : label("error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <h1 className="font-display text-4xl">{label("extract")}</h1>
      <p className="mt-2 max-w-2xl text-moss">{label("tagline")}</p>
      <form onSubmit={(event) => void run(event)} className="mt-8 grid gap-6 lg:grid-cols-2">
        <fieldset className="rounded-2xl border border-line bg-card p-5">
          <legend className="px-1 text-sm">{label("documents")}</legend>
          {documents.length === 0 ? <p className="text-sm text-moss">{label("emptyBody")}</p> : null}
          <ul className="grid gap-2">
            {documents.map((item) => (
              <li key={item.id}>
                <label className="flex items-start gap-3 text-sm">
                  <input
                    type="checkbox"
                    checked={selected.includes(item.id)}
                    onChange={() => toggle(item.id)}
                    className="mt-1"
                  />
                  <span dir="auto">{item.filename}</span>
                </label>
              </li>
            ))}
          </ul>
        </fieldset>
        <div>
          <div className="flex items-center justify-between gap-3">
            <label htmlFor="schema" className="text-sm">
              {label("schema")}
            </label>
            <button type="button" onClick={() => setSchema(EXAMPLE)} className="text-sm text-tide">
              {label("example")}
            </button>
          </div>
          <textarea
            id="schema"
            value={schema}
            onChange={(event) => setSchema(event.target.value)}
            rows={16}
            spellCheck={false}
            className="mt-2 w-full rounded-xl border border-line bg-card p-3 font-mono text-sm"
          />
          <button
            type="submit"
            disabled={busy}
            className="mt-4 rounded-full bg-tide px-5 py-2 text-sm text-card disabled:opacity-50"
          >
            {busy ? label("extracting") : label("run")}
          </button>
        </div>
      </form>
      {error ? (
        <p role="alert" className="mt-4 text-seal">
          {error}
        </p>
      ) : null}
      {result ? (
        <section className="mt-8 rounded-2xl border border-line bg-card p-5 shadow-sheet">
          <h2 className="font-display text-2xl">{label("result")}</h2>
          <p className="mt-1 text-xs uppercase tracking-wide text-moss">
            {label("provider")}: {result.provider}
          </p>
          <dl className="mt-4 grid gap-4 sm:grid-cols-2">
            {Object.entries(result.result).map(([key, value]) => (
              <div key={key}>
                <dt className="text-xs uppercase tracking-wide text-moss">{key.replaceAll("_", " ")}</dt>
                <dd dir="auto" className="mt-1 whitespace-pre-wrap leading-6">
                  {typeof value === "string" ? value || "—" : JSON.stringify(value, null, 2)}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}
    </main>
  );
}
