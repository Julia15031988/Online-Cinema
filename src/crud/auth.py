from sqlalchemy.future import select
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import secrets

from src.database.models.user import (
    User, UserGroup, ActivationToken, PasswordResetToken, RefreshToken
)
from src.security.utils.hash import hash_password
from src.config.settings import settings


async def get_user_by_email(db: AsyncSession, email: str):
    q = await db.execute(select(User).where(User.email == email))
    return q.scalars().first()


async def create_user(db: AsyncSession, email: str, password: str, group_name: str = "USER"):
    existing = await get_user_by_email(db, email)
    if existing:
        return None
    hashed = hash_password(password)
    q = await db.execute(select(UserGroup).where(UserGroup.name == group_name))
    group = q.scalars().first()
    if not group:
        group = UserGroup(name=group_name)
        db.add(group)
        await db.flush()
    user = User(email=email, hashed_password=hashed, group_id=group.id)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def create_activation_token(db: AsyncSession, user: User):
    token = secrets.token_urlsafe(32)
    expires = datetime.now() + timedelta(hours=settings.ACTIVATION_TOKEN_EXPIRE_HOURS)
    await db.execute(delete(ActivationToken).where(ActivationToken.user_id == user.id))
    at = ActivationToken(user_id=user.id, token=token, expires_at=expires)
    db.add(at)
    await db.commit()
    await db.refresh(at)
    return at


async def verify_activation_token(db: AsyncSession, token: str):
    q = await db.execute(select(ActivationToken).where(ActivationToken.token == token))
    at = q.scalars().first()
    if not at or at.expires_at < datetime.now():
        return None
    user_q = await db.execute(select(User).where(User.id == at.user_id))
    user = user_q.scalars().first()
    if user:
        user.is_active = True
        await db.execute(delete(ActivationToken).where(ActivationToken.user_id == user.id))
        await db.commit()
    return user


async def create_refresh_token(db: AsyncSession, user_id: int):
    token, expires = secrets.token_urlsafe(64), datetime.now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    rt = RefreshToken(user_id=user_id, token=token, expires_at=expires)
    db.add(rt)
    await db.commit()
    await db.refresh(rt)
    return rt


async def revoke_refresh_token(db: AsyncSession, token: str):
    await db.execute(delete(RefreshToken).where(RefreshToken.token == token))
    await db.commit()


async def get_refresh_token(db: AsyncSession, token: str):
    q = await db.execute(select(RefreshToken).where(RefreshToken.token == token))
    return q.scalars().first()


async def create_password_reset_token(db: AsyncSession, user: User):
    token = secrets.token_urlsafe(32)
    expires = datetime.now() + timedelta(hours=settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS)
    await db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
    pr = PasswordResetToken(user_id=user.id, token=token, expires_at=expires)
    db.add(pr)
    await db.commit()
    await db.refresh(pr)
    return pr


async def verify_password_reset_token(db: AsyncSession, token: str):
    q = await db.execute(select(PasswordResetToken).where(PasswordResetToken.token == token))
    pr = q.scalars().first()
    if not pr or pr.expires_at < datetime.now():
        return None
    return pr.user
