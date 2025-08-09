""" Database models for the application. """
from typing import Optional, List
from sqlmodel import Field, SQLModel, Relationship


class User(SQLModel, table=True):
    """ User model for the database. """
    id: Optional[int] = Field(primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    currency: str = Field(
        default="EUR", description="User's preferred currency")
    positions: List["AssetPosition"] = Relationship(back_populates="owner")


class AssetPosition(SQLModel, table=True):
    """ Asset position model for the database. """
    id: Optional[int] = Field(primary_key=True)

    ticker: str
    quantity: float
    user_id: int = Field(foreign_key="user.id")

    owner: User = Relationship(back_populates="positions")
