from datetime import datetime
from decimal import Decimal
from typing import List

from pydantic import BaseModel, Field

from src.schemas.movies import GenreSchema


class MovieInCart(BaseModel):
    """Schema for a movie item within the cart."""
    id: int = Field(..., description="The unique ID of the movie.")
    name: str = Field(..., description="The title of the movie.")
    price: Decimal = Field(..., description="The price of the movie.")
    year: int = Field(..., description="The release year of the movie.")
    genres: List[GenreSchema] = Field(..., description="A list of genres associated with the movie.")

    class Config:
        from_attributes = True


class CartItemSchema(BaseModel):
    """Schema for a single item in the shopping cart."""
    id: int = Field(..., description="The unique ID of the cart item.")
    movie: MovieInCart = Field(..., description="The movie details for the item in the cart.")
    added_at: datetime = Field(..., description="The date and time the movie was added to the cart.")

    class Config:
        from_attributes = True


class CartSchema(BaseModel):
    """Schema for the entire shopping cart."""
    id: int = Field(..., description="The unique ID of the cart.")
    items: List[CartItemSchema] = Field(..., description="A list of all items currently in the cart.")

    class Config:
        from_attributes = True


class CartResponse(BaseModel):
    """Schema for a generic response message."""
    message: str = Field(..., description="A message confirming the result of the operation.")
