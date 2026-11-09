import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    owner_id: uuid.UUID
    created_at: datetime


class MeOut(BaseModel):
    user: UserOut
    workspace: WorkspaceOut
    role: str
    key_prefix: str
    providers: list[str]


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class WorkspaceCreated(BaseModel):
    workspace: WorkspaceOut
    api_key: str


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    name: str = Field(min_length=1, max_length=200)
    role: str = "member"


class UserCreated(BaseModel):
    user: UserOut
    api_key: str


class ApiKeyCreate(BaseModel):
    name: str = Field(default="key", min_length=1, max_length=200)


class ApiKeyCreated(BaseModel):
    id: uuid.UUID
    prefix: str
    name: str
    api_key: str


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    media_type: str
    byte_size: int
    language: str | None
    status: str
    page_count: int
    error: str | None
    summary_short: str | None
    summary_provider: str | None = None
    created_at: datetime


class DocumentDetail(DocumentOut):
    summary_detailed: str | None


class PageOut(BaseModel):
    page: int
    text: str


class DocumentText(BaseModel):
    document_id: uuid.UUID
    language: str | None
    pages: list[PageOut]


class SummaryOut(BaseModel):
    short: str
    detailed: str
    provider: str | None
    language: str | None


class TranslationIn(BaseModel):
    target_language: str = Field(pattern="^(ar|fr|en)$")


class TranslationOut(BaseModel):
    language: str
    direction: str
    paragraphs: list[str]
    text: str
    provider: str


class QuestionIn(BaseModel):
    document_ids: list[uuid.UUID] = Field(min_length=1, max_length=10)
    question: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=12)


class CitationOut(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    page: int
    quote: str


class AnswerOut(BaseModel):
    id: uuid.UUID
    question: str
    answer: str
    citations: list[CitationOut]
    provider: str
    created_at: datetime


class ExtractIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    document_ids: list[uuid.UUID] = Field(min_length=1, max_length=10)
    json_schema: dict[str, Any] = Field(alias="schema")


class ExtractOut(BaseModel):
    id: uuid.UUID
    result: dict[str, Any]
    provider: str
    created_at: datetime


class UsageRow(BaseModel):
    provider: str
    operation: str
    calls: int
    prompt_tokens: int
    completion_tokens: int
    avg_latency_ms: float


class DocumentList(BaseModel):
    items: list[DocumentOut]
    total: int
