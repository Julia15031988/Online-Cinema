import enum
from src.database.models.base import Base
from sqlalchemy.orm import relationship
from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    ForeignKey,
    DateTime,
    Text,
    Enum,
    UniqueConstraint,
)


class GenderEnum(enum.Enum):
    MAN = "MAN"
    WOMAN = "WOMAN"


class UserGroupEnum(enum.Enum):
    USER = "USER"
    MODERATOR = "MODERATOR"
    ADMIN = "ADMIN"


class UserGroup(Base):
    __tablename__ = "user_groups"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String(50), nullable=False)

    users = relationship("User", back_populates="group")


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(320), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.utcnow)
    group_id = Column(Integer, ForeignKey("user_groups.id"), nullable=False)

    group = relationship("UserGroup", back_populates="users")

    comments = relationship(
        "Comment", back_populates="user", cascade="all, delete-orphan"
    )
    reactions = relationship("MovieReaction", back_populates="user")

    profile = relationship("UserProfile", uselist=False, back_populates="user")
    activation_token = relationship(
        "ActivationToken",
        uselist=False,
        back_populates="user",
        cascade="all, delete-orphan",
    )
    password_reset_token = relationship(
        "PasswordResetToken",
        uselist=False,
        back_populates="user",
        cascade="all, delete-orphan",
    )
    refresh_tokens = relationship(
        "RefreshToken", back_populates="user", cascade="all, delete-orphan"
    )

    cart = relationship("Cart", back_populates="user", uselist=False)
    orders = relationship("Order", back_populates="user")
    purchases = relationship("Purchase", back_populates="user")
    payments = relationship("Payment", back_populates="user")


class UserProfile(Base):
    __tablename__ = "user_profiles"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    first_name = Column(String(50))
    last_name = Column(String(50))
    avatar = Column(Text)
    gender = Column(Enum(GenderEnum))
    date_of_birth = Column(DateTime)
    info = Column(Text)

    user = relationship("User", back_populates="profile")


class ActivationToken(Base):
    __tablename__ = "activation_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)

    user = relationship("User", back_populates="activation_token")


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)

    user = relationship("User", back_populates="password_reset_token")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)

    user = relationship("User", back_populates="refresh_tokens")
