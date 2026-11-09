from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter(
    "qalam_http_requests_total",
    "HTTP requests served by the API.",
    ["method", "path", "status"],
)
HTTP_LATENCY = Histogram(
    "qalam_http_request_duration_seconds",
    "HTTP request latency.",
    ["path"],
)
LLM_REQUESTS = Counter(
    "qalam_llm_requests_total",
    "Language model calls by provider and outcome.",
    ["provider", "operation", "outcome"],
)
LLM_LATENCY = Histogram(
    "qalam_llm_latency_seconds",
    "Language model latency, including retries on that provider.",
    ["provider", "operation"],
)
LLM_TOKENS = Counter(
    "qalam_llm_tokens_total",
    "Tokens reported by the provider, or estimated when the provider omits usage.",
    ["provider", "direction"],
)
INGEST_LATENCY = Histogram(
    "qalam_ingest_duration_seconds",
    "Time spent extracting, chunking and embedding one document.",
)
DOCUMENTS = Counter(
    "qalam_documents_total",
    "Documents that finished ingestion.",
    ["outcome"],
)
