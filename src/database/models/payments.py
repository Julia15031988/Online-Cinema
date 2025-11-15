from sqlalchemy import Column, Integer, ForeignKey, Enum, Numeric, String, DateTime, func
from sqlalchemy.orm import relationship, Mapped, mapped_column
from src.database.models import User
import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    ForeignKey,
    DateTime,
    Enum as SQLAlchemyEnum,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database import Base
from src.database.models.user import User
from src.database.models.orders import Order, OrderItem


class PaymentStatus(str, enum.Enum):
    successful = "successful"
    canceled = "canceled"
    refunded = "refunded"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), nullable=False, default=PaymentStatus.successful)
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    external_payment_id: Mapped[str] = mapped_column(String, nullable=True)

    user = relationship("User", back_populates="payments")
    order = relationship("Order", back_populates="payments")
    items = relationship("PaymentItem", back_populates="payment", cascade="all, delete-orphan")


class PaymentItem(Base):
    __tablename__ = "payment_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id"), nullable=False)
    order_item_id: Mapped[int] = mapped_column(ForeignKey("order_items.id"), nullable=False)
    price_at_payment: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    payment = relationship("Payment", back_populates="items")
    order_item = relationship("OrderItem", back_populates="payment_items")
