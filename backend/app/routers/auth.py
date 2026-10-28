from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import audit
from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.ratelimit import login_failures
from app.schemas import Credentials, TokenOut, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(tags=["auth"])

MAX_FAILED_LOGINS = 5
LOCKOUT_SECONDS = 900


@router.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(body: Credentials, db: Session = Depends(get_db)) -> User:
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:  # two simultaneous signups with the same email
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    audit.record(db, user.id, "registered")
    return user


@router.post("/auth/login", response_model=TokenOut)
def login(body: Credentials, db: Session = Depends(get_db)) -> TokenOut:
    key = body.email.lower()
    # Checked before hashing, and counted per email whether or not the account exists,
    # so the response never reveals which emails are registered.
    if login_failures.count(key, LOCKOUT_SECONDS) >= MAX_FAILED_LOGINS:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many failed attempts. Try again in 15 minutes.",
            headers={"Retry-After": str(LOCKOUT_SECONDS)},
        )
    user = db.scalar(select(User).where(User.email == key))
    ok = verify_password(body.password, user.password_hash if user else None)
    if not user or not ok:
        login_failures.add(key)
        audit.record(db, user.id if user else None, "login_failed")
        # Same message for unknown email and wrong password.
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    login_failures.clear(key)
    audit.record(db, user.id, "login")
    return TokenOut(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user
