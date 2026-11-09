import uuid

from sqlalchemy.orm import Session

from qalam.llm.types import Completion
from qalam.models import UsageEvent


def record_usage(
    session: Session,
    workspace_id: uuid.UUID | None,
    operation: str,
    completion: Completion,
) -> None:
    session.add(
        UsageEvent(
            workspace_id=workspace_id,
            operation=operation,
            provider=completion.provider,
            model=completion.model,
            prompt_tokens=completion.prompt_tokens,
            completion_tokens=completion.completion_tokens,
            latency_ms=completion.latency_ms,
        )
    )
