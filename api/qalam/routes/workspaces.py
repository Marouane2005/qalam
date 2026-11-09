from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from qalam.auth import Principal, create_user_in_workspace, issue_key, new_workspace_for
from qalam.deps import get_principal, get_session
from qalam.errors import AppError
from qalam.models import Membership, UsageEvent, Workspace
from qalam.schemas import (
    ApiKeyCreate,
    ApiKeyCreated,
    MeOut,
    UsageRow,
    UserCreate,
    UserCreated,
    UserOut,
    WorkspaceCreate,
    WorkspaceCreated,
    WorkspaceOut,
)

router = APIRouter(prefix="/v1", tags=["workspaces"])


def _require_owner(principal: Principal) -> None:
    if principal.membership.role != "owner":
        raise AppError("forbidden", "Only a workspace owner can do that.", 403)


@router.get("/me", response_model=MeOut)
def me(request: Request, principal: Principal = Depends(get_principal)) -> MeOut:
    return MeOut(
        user=UserOut.model_validate(principal.user),
        workspace=WorkspaceOut.model_validate(principal.workspace),
        role=principal.membership.role,
        key_prefix=principal.api_key.prefix,
        providers=list(request.app.state.llm.provider_names),
    )


@router.get("/workspaces", response_model=list[WorkspaceOut])
def list_workspaces(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> list[Workspace]:
    return list(
        session.scalars(
            select(Workspace)
            .join(Membership, Membership.workspace_id == Workspace.id)
            .where(Membership.user_id == principal.user.id)
            .order_by(Workspace.created_at)
        ).all()
    )


@router.post("/workspaces", response_model=WorkspaceCreated, status_code=201)
def create_workspace(
    body: WorkspaceCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> WorkspaceCreated:
    workspace, raw = new_workspace_for(session, principal.user, body.name.strip())
    return WorkspaceCreated(workspace=WorkspaceOut.model_validate(workspace), api_key=raw)


@router.post("/workspaces/{workspace_id}/api-keys", response_model=ApiKeyCreated, status_code=201)
def create_api_key(
    workspace_id: str,
    body: ApiKeyCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> ApiKeyCreated:
    _require_owner(principal)
    if str(principal.workspace.id) != workspace_id:
        raise AppError("not_found", "Workspace not found.", 404)
    record, raw = issue_key(
        session,
        user=principal.user,
        workspace=principal.workspace,
        name=body.name.strip(),
    )
    session.commit()
    return ApiKeyCreated(id=record.id, prefix=record.prefix, name=record.name, api_key=raw)


@router.post("/users", response_model=UserCreated, status_code=201)
def invite_user(
    body: UserCreate,
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> UserCreated:
    _require_owner(principal)
    if body.role not in {"owner", "member"}:
        raise AppError("invalid_role", "Role must be owner or member.", 422)
    user, raw = create_user_in_workspace(
        session,
        email=body.email.strip().lower(),
        name=body.name.strip(),
        workspace=principal.workspace,
        role=body.role,
    )
    return UserCreated(user=UserOut.model_validate(user), api_key=raw)


@router.get("/usage", response_model=list[UsageRow])
def usage(
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_session),
) -> list[UsageRow]:
    rows = session.execute(
        select(
            UsageEvent.provider,
            UsageEvent.operation,
            func.count(),
            func.coalesce(func.sum(UsageEvent.prompt_tokens), 0),
            func.coalesce(func.sum(UsageEvent.completion_tokens), 0),
            func.coalesce(func.avg(UsageEvent.latency_ms), 0),
        )
        .where(UsageEvent.workspace_id == principal.workspace.id)
        .group_by(UsageEvent.provider, UsageEvent.operation)
        .order_by(UsageEvent.operation)
    ).all()
    return [
        UsageRow(
            provider=provider,
            operation=operation,
            calls=int(calls),
            prompt_tokens=int(prompt_tokens),
            completion_tokens=int(completion_tokens),
            avg_latency_ms=float(avg_latency),
        )
        for provider, operation, calls, prompt_tokens, completion_tokens, avg_latency in rows
    ]
