""" Client models for the application. """
from pydantic import BaseModel


class AssetPositionRequest(BaseModel):
    """ Asset position request model for the database. """
    ticker: str
    quantity: float
