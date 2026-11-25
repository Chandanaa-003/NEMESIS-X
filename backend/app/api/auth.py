from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.models.user import User
from app.schemas.user import (
    AuthTokenResponse,
    UserLoginRequest,
    UserPublic,
    UserRegisterRequest,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
def register_user(payload: UserRegisterRequest, db: Session = Depends(get_db)) -> AuthTokenResponse:
    """Create a new user account with an Argon2-hashed password and return a JWT token."""
    try:
        existing = db.query(User).filter(User.email == payload.email).first()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while checking existing account.",
        ) from exc

    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        is_active=True,
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while creating user account.",
        ) from exc

    access_token = create_access_token(subject=str(user.id))
    return AuthTokenResponse(
        access_token=access_token,
        user=UserPublic.model_validate(user),
    )


@router.post(
    "/login",
    response_model=AuthTokenResponse,
    summary="Authenticate user and issue JWT token",
)
def login_user(payload: UserLoginRequest, db: Session = Depends(get_db)) -> AuthTokenResponse:
    """Verify email and password credentials and return a JWT access token."""
    try:
        user = db.query(User).filter(User.email == payload.email).first()
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while verifying credentials.",
        ) from exc

    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This user account is inactive.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(subject=str(user.id))
    return AuthTokenResponse(
        access_token=access_token,
        user=UserPublic.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserPublic,
    summary="Get currently authenticated user",
)
def read_current_user(current_user: User = Depends(get_current_user)) -> UserPublic:
    """Return the authenticated user's profile."""
    return UserPublic.model_validate(current_user)
