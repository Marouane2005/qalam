import hashlib
import secrets
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from qalam.models import ApiKey, Membership, User, Workspace, utcnow

GUEST_EMAIL_SUFFIX = "@guest.qalam.invalid"


def is_guest(user: User) -> bool:
    return user.email.endswith(GUEST_EMAIL_SUFFIX)


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def generate_api_key() -> str:
    return "qlm_" + secrets.token_urlsafe(32)


def key_prefix(raw: str) -> str:
    return raw[:8]


@dataclass
class Principal:
    user: User
    workspace: Workspace
    membership: Membership
    api_key: ApiKey


def lookup_principal(session: Session, raw_key: str) -> Principal | None:
    if not raw_key:
        return None
    row = session.execute(
        select(ApiKey, User, Workspace, Membership)
        .join(User, ApiKey.user_id == User.id)
        .join(Workspace, ApiKey.workspace_id == Workspace.id)
        .join(
            Membership,
            (Membership.user_id == User.id) & (Membership.workspace_id == Workspace.id),
        )
        .where(ApiKey.key_hash == hash_key(raw_key), ApiKey.revoked_at.is_(None))
    ).first()
    if row is None:
        return None
    api_key, user, workspace, membership = row
    api_key.last_used_at = utcnow()
    session.commit()
    return Principal(user=user, workspace=workspace, membership=membership, api_key=api_key)


def issue_key(
    session: Session,
    *,
    user: User,
    workspace: Workspace,
    name: str,
) -> tuple[ApiKey, str]:
    raw = generate_api_key()
    record = ApiKey(
        user_id=user.id,
        workspace_id=workspace.id,
        name=name,
        prefix=key_prefix(raw),
        key_hash=hash_key(raw),
    )
    session.add(record)
    session.flush()
    return record, raw


def bootstrap_account(
    session: Session,
    *,
    email: str,
    name: str,
    workspace_name: str,
    api_key: str,
) -> ApiKey | None:
    if not email or not api_key:
        return None
    existing = session.scalar(select(ApiKey).where(ApiKey.key_hash == hash_key(api_key)))
    if existing is not None:
        return existing
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, name=name)
        session.add(user)
        session.flush()
    workspace = session.scalar(select(Workspace).where(Workspace.owner_id == user.id))
    if workspace is None:
        workspace = Workspace(name=workspace_name, owner_id=user.id)
        session.add(workspace)
        session.flush()
        session.add(Membership(user_id=user.id, workspace_id=workspace.id, role="owner"))
    record = ApiKey(
        user_id=user.id,
        workspace_id=workspace.id,
        name="bootstrap",
        prefix=key_prefix(api_key),
        key_hash=hash_key(api_key),
    )
    session.add(record)
    session.commit()
    return record


def create_user_in_workspace(
    session: Session,
    *,
    email: str,
    name: str,
    workspace: Workspace,
    role: str = "member",
) -> tuple[User, str]:
    user = session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, name=name)
        session.add(user)
        session.flush()
    membership = session.scalar(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.workspace_id == workspace.id,
        )
    )
    if membership is None:
        session.add(Membership(user_id=user.id, workspace_id=workspace.id, role=role))
        session.flush()
    _record, raw = issue_key(session, user=user, workspace=workspace, name=f"{name} key")
    session.commit()
    return user, raw


def new_workspace_for(session: Session, owner: User, name: str) -> tuple[Workspace, str]:
    workspace = Workspace(id=uuid.uuid4(), name=name, owner_id=owner.id)
    session.add(workspace)
    session.flush()
    session.add(Membership(user_id=owner.id, workspace_id=workspace.id, role="owner"))
    _record, raw = issue_key(session, user=owner, workspace=workspace, name=f"{name} key")
    session.commit()
    return workspace, raw


def create_guest(session: Session) -> tuple[User, Workspace, str]:
    """Create a private guest user, workspace, membership and API key."""
    user = User(
        email=f"guest-{uuid.uuid4().hex}{GUEST_EMAIL_SUFFIX}",
        name="Guest",
    )
    session.add(user)
    session.flush()
    workspace = Workspace(name="My library", owner_id=user.id)
    session.add(workspace)
    session.flush()
    session.add(Membership(user_id=user.id, workspace_id=workspace.id, role="owner"))
    _record, raw = issue_key(session, user=user, workspace=workspace, name="guest key")
    session.commit()
    return user, workspace, raw
