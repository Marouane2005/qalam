export type Locale = "en" | "fr" | "ar";

export type DocumentStatus = "queued" | "processing" | "ready" | "failed";

export type Me = {
  user: { id: string; email: string; name: string };
  workspace: { id: string; name: string };
  role: string;
  key_prefix: string;
  providers: string[];
};

export type DocumentItem = {
  id: string;
  filename: string;
  media_type: string;
  byte_size: number;
  language: string | null;
  status: DocumentStatus;
  page_count: number;
  error: string | null;
  summary_short: string | null;
  summary_provider: string | null;
  summary_detailed?: string | null;
  created_at: string;
};

export type DocumentList = {
  items: DocumentItem[];
  total: number;
};

export type PageText = { page: number; text: string };

export type DocumentText = {
  document_id: string;
  language: string | null;
  pages: PageText[];
};

export type Summary = {
  short: string;
  detailed: string;
  provider: string | null;
  language: string | null;
};

export type Translation = {
  language: string;
  direction: "rtl" | "ltr";
  paragraphs: string[];
  text: string;
  provider: string;
};

export type Citation = {
  chunk_id: string;
  document_id: string;
  filename: string;
  page: number;
  quote: string;
};

export type Answer = {
  id: string;
  question: string;
  answer: string;
  citations: Citation[];
  provider: string;
  created_at: string;
};

export type Extraction = {
  id: string;
  result: Record<string, unknown>;
  provider: string;
  created_at: string;
};
