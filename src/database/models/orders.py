from datetime import datetime
import enum

from sqlalchemy import ForeignKey, DECIMAL, Enum, DateTime, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base


class OrderStatusEnum(str, enum.Enum):
    Pending = "Pending"
    Paid = "Paid"
    Cancelled  = "Cancelled"


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at : Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now(),
        server_default=text("(datetime('now'))")
    )
    status: Mapped[OrderStatusEnum] = mapped_column(Enum(OrderStatusEnum), nullable=False)
    total_amount: Mapped[float] = mapped_column(DECIMAL(10,2), nullable=False)

    user: Mapped["User"] = relationship(back_populates="orders")
    item: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "orderitems"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"))
    price_at_order: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")
    movie: Mapped["Movie"] = relationship(back_populates="order_items")
