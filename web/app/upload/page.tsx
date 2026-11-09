"use client";

import Link from "next/link";
import { useState } from "react";

import { useApp } from "@/components/Providers";
import { api, ApiError } from "@/lib/api";
import type { DocumentItem } from "@/lib/types";

type Row = { name: string; id?: string; error?: string };

export default function UploadPage() {
  const { apiKey, label } = useApp();
  const [rows, setRows] = useState<Row[]>([]);
  const [busy, setBusy] = useState(false);
  const [over, setOver] = useState(false);

  async function send(files: File[]) {
    if (!apiKey || files.length === 0) return;
    setBusy(true);
    const next: Row[] = [];
    for (const file of files) {
      const body = new FormData();
      body.set("file", file);
      try {
        const document = await api<DocumentItem>("/v1/documents", apiKey, { method: "POST", body });
        next.push({ name: file.name, id: document.id });
      } catch (error) {
        next.push({
          name: file.name,
          error: error instanceof ApiError ? error.message : label("error"),
        });
      }
    }
    setRows((current) => [...next, ...current]);
    setBusy(false);
  }

  return (
    <main>
      <h1 className="font-display text-4xl">{label("upload")}</h1>
      <p className="mt-2 max-w-xl text-moss">{label("dropBody")}</p>
      <label
        onDragOver={(event) => {
          event.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={(event) => {
          event.preventDefault();
          setOver(false);
          void send(Array.from(event.dataTransfer.files));
        }}
        className={`mt-8 flex cursor-pointer flex-col items-center rounded-2xl border border-dashed px-6 py-16 text-center ${
          over ? "border-tide bg-card" : "border-line bg-card/60"
        }`}
      >
        <span className="font-display text-3xl">{label("dropTitle")}</span>
        <span className="mt-2 text-sm text-moss">{busy ? label("uploading") : label("browse")}</span>
        <input
          type="file"
          className="sr-only"
          multiple
          accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.webp,.docx,.txt,application/pdf,text/plain"
          onChange={(event) => {
            const files = event.target.files ? Array.from(event.target.files) : [];
            event.target.value = "";
            void send(files);
          }}
        />
      </label>
      <ul className="mt-6 grid gap-3">
        {rows.map((row) => (
          <li key={`${row.name}-${row.id || row.error}`} className="rounded-xl border border-line bg-card px-4 py-3">
            <p dir="auto">{row.name}</p>
            {row.id ? (
              <Link href={`/documents/${row.id}`} className="text-sm text-tide underline-offset-2 hover:underline">
                {label("library")}
              </Link>
            ) : (
              <p role="alert" className="text-sm text-seal">
                {row.error}
              </p>
            )}
          </li>
        ))}
      </ul>
    </main>
  );
}
