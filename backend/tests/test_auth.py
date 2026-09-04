from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from jwt import InvalidTokenError
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, require_roles
from app.auth.security import create_access_token, decode_access_token, hash_password, verify_password
from app.auth.seed import DEMO_USERS, seed_demo_users
from app.core.database import SessionLocal
from app.main import app
from app.models.enums import UserRole
from app.models.identity import User

TEST_EMAIL_PREFIX = "auth-test-"


@pytest.fixture
def session() -> Session:
    if SessionLocal is None:
        pytest.skip("HONEY_CHAIN_DATABASE_URL is not configured.")

    with SessionLocal() as database_session:
        database_session.execute(delete(User).where(User.email.like(f"{TEST_EMAIL_PREFIX}%")))
        database_session.execute(delete(User).where(User.email.in_([email for _, email, _ in DEMO_USERS])))
        database_session.commit()
        try:
            yield database_session
        finally:
            database_session.execute(delete(User).where(User.email.like(f"{TEST_EMAIL_PREFIX}%")))
            database_session.execute(delete(User).where(User.email.in_([email for _, email, _ in DEMO_USERS])))
            database_session.commit()


def _create_user(
    session: Session,
    *,
    email: str,
    password: str = "correct-password",
    role: UserRole = UserRole.BEEKEEPER,
    is_active: bool = True,
) -> User:
    user = User(
        name="Authentication Test User",
        email=email.lower(),
        password_hash=hash_password(password),
        role=role,
        is_active=is_active,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_password_hashing_and_verification() -> None:
    hashed_password = hash_password("correct-password")

    assert hashed_password.startswith("$argon2id$")
    assert verify_password("correct-password", hashed_password)
    assert not verify_password("incorrect-password", hashed_password)


def test_login_success_and_no_password_hash_in_response(session: Session) -> None:
    _create_user(session, email="auth-test-login@example.test")

    response = TestClient(app).post(
        "/auth/login",
        data={"username": "AUTH-TEST-LOGIN@EXAMPLE.TEST", "password": "correct-password"},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]
    assert "password_hash" not in response.text


def test_login_rejects_invalid_credentials(session: Session) -> None:
    _create_user(session, email="auth-test-invalid@example.test")

    response = TestClient(app).post(
        "/auth/login",
        data={"username": "auth-test-invalid@example.test", "password": "incorrect-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect email or password"}


def test_inactive_user_cannot_login(session: Session) -> None:
    _create_user(session, email="auth-test-inactive@example.test", is_active=False)

    response = TestClient(app).post(
        "/auth/login",
        data={"username": "auth-test-inactive@example.test", "password": "correct-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Incorrect email or password"}


def test_jwt_validation_rejects_expired_and_invalid_tokens() -> None:
    token = create_access_token(uuid4(), UserRole.ADMIN)

    assert decode_access_token(token)["role"] == UserRole.ADMIN.value
    with pytest.raises(InvalidTokenError):
        decode_access_token(create_access_token(uuid4(), UserRole.ADMIN, timedelta(seconds=-1)))
    with pytest.raises(InvalidTokenError):
        decode_access_token("not-a-jwt")


def test_current_user_dependency_returns_database_user(session: Session) -> None:
    user = _create_user(session, email="auth-test-current@example.test", role=UserRole.PROCESSOR)
    token = create_access_token(user.id, user.role)
    protected_app = FastAPI()

    @protected_app.get("/current")
    def current_user_endpoint(current_user: User = Depends(get_current_user)) -> dict[str, str]:
        return {"id": str(current_user.id), "role": current_user.role.value}

    response = TestClient(protected_app).get(
        "/current", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json() == {"id": str(user.id), "role": "PROCESSOR"}


def test_role_dependency_allows_and_rejects_roles(session: Session) -> None:
    admin = _create_user(session, email="auth-test-admin@example.test", role=UserRole.ADMIN)
    beekeeper = _create_user(session, email="auth-test-beekeeper@example.test", role=UserRole.BEEKEEPER)
    protected_app = FastAPI()

    @protected_app.get("/admin")
    def admin_endpoint(current_user: User = Depends(require_roles(UserRole.ADMIN))) -> dict[str, str]:
        return {"role": current_user.role.value}

    client = TestClient(protected_app)
    admin_response = client.get(
        "/admin", headers={"Authorization": f"Bearer {create_access_token(admin.id, admin.role)}"}
    )
    beekeeper_response = client.get(
        "/admin",
        headers={"Authorization": f"Bearer {create_access_token(beekeeper.id, beekeeper.role)}"},
    )

    assert admin_response.status_code == 200
    assert beekeeper_response.status_code == 403
    assert beekeeper_response.json() == {"detail": "Insufficient permissions"}


def test_demo_seed_is_idempotent_and_does_not_overwrite_existing_user(session: Session) -> None:
    existing = _create_user(
        session,
        email="demo.admin@honeychain.local",
        password="existing-password",
        role=UserRole.ADMIN,
    )
    original_hash = existing.password_hash

    first_run = seed_demo_users(session, "demo-password")
    second_run = seed_demo_users(session, "demo-password")
    users = session.query(User).filter(User.email.in_([email for _, email, _ in DEMO_USERS])).all()

    assert len(first_run) == 2
    assert second_run == []
    assert len(users) == 3
    assert session.get(User, existing.id).password_hash == original_hash
