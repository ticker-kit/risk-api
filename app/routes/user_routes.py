""" User routes for the application. """
from typing import Optional
from dataclasses import dataclass
import re
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
from app.db import get_session

from app.models.db_models import User
from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.yfinance_service import yfinance_service

router = APIRouter()


@dataclass
class HomeCurrencyResponse:
    """Response for home currency endpoints."""
    new_currency: str
    success: bool
    message: Optional[str] = None
    recommendations: Optional[list[str]] = None


@dataclass
class AuthResponse:
    """Response for auth endpoints."""
    success: bool
    message: str
    access_token: str | None

    def to_dict(self):
        """Convert to dictionary."""
        return {
            "success": self.success,
            "message": self.message,
            "access_token": self.access_token
        }


def normalize_username(username: str) -> str:
    """Normalize username: lowercase, remove spaces, only alphanumeric, max 15 chars."""
    username = username.lower().replace(' ', '')
    username = re.sub(r'[^a-z0-9]', '', username)
    return username[:15]


def is_valid_username(username: str) -> bool:
    """Check if username is only alphanumeric, no spaces, max 15 chars, not empty."""
    return username is not None and username.isalnum() and len(username) > 2 and len(username) <= 15


@router.post("/register")
def register(form: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    """ Register a new user. """
    norm_username = normalize_username(form.username)
    # Validate username
    if not is_valid_username(norm_username):
        return AuthResponse(
            success=False,
            message="Invalid username: must be alphanumeric, no spaces, min 3 chars, max 15 chars.",
            access_token=None
        ).to_dict()

    # Check if username already exists
    try:
        existing_user = session.exec(select(User).where(
            User.username == norm_username)).first()
    except Exception:
        return AuthResponse(
            success=False,
            message="Something went wrong while checking if username exists",
            access_token=None
        ).to_dict()

    if existing_user:
        return AuthResponse(
            success=False,
            message="Username already exists",
            access_token=None
        ).to_dict()

    # Create new user
    try:
        new_user = User(username=norm_username,
                        hashed_password=hash_password(form.password))
        session.add(new_user)
        session.commit()
        session.refresh(new_user)
        return AuthResponse(
            success=True,
            message="User registered successfully",
            access_token=create_access_token({"sub": norm_username})
        ).to_dict()

    except Exception:
        session.rollback()
        return AuthResponse(
            success=False,
            message="Something went wrong while registering user",
            access_token=None
        ).to_dict()


@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    """ Login a user. """
    norm_username = normalize_username(form.username)

    # Check if username exists
    try:
        user = session.exec(select(User).where(
            User.username == norm_username)).first()
    except Exception:
        return AuthResponse(
            success=False,
            message="Something went wrong while fetching user",
            access_token=None
        ).to_dict()

    if user is None or not verify_password(form.password, user.hashed_password):
        return AuthResponse(
            success=False,
            message="Invalid credentials",
            access_token=None
        ).to_dict()

    return AuthResponse(
        success=True,
        message="Login successful",
        access_token=create_access_token({"sub": user.username})
    ).to_dict()


@router.get("/home_currency")
async def update_home_currency(
    code: str,
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user)):
    """ Update the home currency for a user. """

    # 0. normalize currency
    input_currency = code.upper().strip()

    # 1. get current user currency
    current_currency = "ZMB"

    # 2. check not the same
    if current_currency == input_currency:
        raise HTTPException(
            status_code=400, detail="Input currency is the same as current currency")

    # 3. check its 3 latin characters
    if not re.match(r'^[A-Z]{3}$', input_currency):
        raise HTTPException(
            status_code=400, detail="Invalid currency format")

    if input_currency == "USD" or input_currency == "EUR":
        return HomeCurrencyResponse(
            new_currency=input_currency,
            success=True,
        ).__dict__

    validation_ticker_eur = f"EUR{input_currency}=X"

    validated_currency = await yfinance_service.validate_ticker(validation_ticker_eur)

    is_valid_currency = validated_currency is not None

    if is_valid_currency:
        return HomeCurrencyResponse(
            new_currency=input_currency,
            success=True,
        ).__dict__

    else:
        # get recommendations
        recommendations_quotes = await yfinance_service.search_tickers(
            validation_ticker_eur, fuzzy=True)

        recommendations = list(set(
            [item["longname"].split("/")[1] for item in recommendations_quotes
                if item["quoteType"] == "CURRENCY"]))

        return HomeCurrencyResponse(
            new_currency=input_currency,
            success=False,
            message=f"Currency {input_currency} not found.",
            recommendations=recommendations
        ).__dict__


@router.get("/users")
def list_users(
        session: Session = Depends(get_session),
        current_user: User = Depends(get_current_user)):
    """ List all users. """
    # Check if user has admin privileges (currently hardcoded to gooneraki)
    # TODO: Replace with proper role-based access control
    if current_user.username != "gooneraki":
        raise HTTPException(
            status_code=403, detail="Insufficient permissions to access user list")

    try:
        users = session.exec(select(User)).all()
        return [{"id": user.id, "username": user.username} for user in users]
    except Exception as e:
        raise HTTPException(
            status_code=500, detail="Something went wrong while fetching users") from e
