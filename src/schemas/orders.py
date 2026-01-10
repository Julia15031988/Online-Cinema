from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict


class OrderMovieSchema(BaseModel):
    movie_id: int = Field(..., description="ID of the movie in the order.")
    name: str = Field(..., description="Name of the movie.")
    price_at_order: Decimal = Field(
        ..., description="Price of the movie at the time of order."
    )

    model_config = ConfigDict(from_attributes=True)


class OrderResponseSchema(BaseModel):
    id: int
    user_id: int
    created_at: datetime
    status: str
    total_amount: Decimal
    items: List[OrderMovieSchema]

    model_config = ConfigDict(from_attributes=True)


class OrderListItemSchema(BaseModel):
    id: int
    user_id: int
    created_at: datetime
    status: str
    total_amount: Decimal
    movies: List[str] = Field(..., description="List of movie names in the order.")

    model_config = ConfigDict(from_attributes=True)


class OrderListResponseSchema(BaseModel):
    orders: List[OrderListItemSchema]
    prev_page: Optional[str] = None
    next_page: Optional[str] = None
    total_pages: int
    total_items: int

    model_config = ConfigDict(from_attributes=True)
