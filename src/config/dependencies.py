import os
import re
from typing import Awaitable, Callable
from fastapi import Depends, HTTPException, Request, UploadFile, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from src.database.session import get_db
from src.database.models.user import (
    User,
    UserGroupEnum,
    UserGroup,
    UserProfile,
    GenderEnum,
)
from src.security import get_token
from src.security.token_manager import JWTAuthManager
from src.security.interfaces import JWTAuthManagerInterface
from src.config.settings import settings, get_settings, TestingSettings, Settings
from src.config.settings import BaseAppSettings
from src.exceptions import BaseSecurityError, TokenExpiredError, S3FileUploadError
from src.notifications.emails import EmailSenderInterface, EmailSender
from src.exceptions.storage import S3StorageInterface, S3StorageClient


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_jwt_auth_manager() -> JWTAuthManager:
    return JWTAuthManager(
        secret_key_access=settings.SECRET_KEY_ACCESS,
        secret_key_refresh=settings.SECRET_KEY_REFRESH,
        algorithm=settings.JWT_ALGORITHM,
    )


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    jwt: JWTAuthManager = Depends(get_jwt_auth_manager),
):
    try:
        payload = jwt.decode_access_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload"
        )
    q = await db.execute(select(User).where(User.id == user_id))
    user = q.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user


def get_current_admin(user: User = Depends(get_current_user)):
    if user.group_id == 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission"
        )
    return user


def get_accounts_email_notificator(
    settings: BaseAppSettings = Depends(get_settings),
) -> EmailSenderInterface:
    """
    Retrieve an instance of the EmailSenderInterface configured with the application settings.

    This function creates an EmailSender using the provided settings, which include details such as the email host,
    port, credentials, TLS usage, and the directory and filenames for email templates. This allows the application
    to send various email notifications (e.g., activation, password reset) as required.

    Args:
        settings (BaseAppSettings, optional): The application settings,
        provided via dependency injection from `get_settings`.

    Returns:
        EmailSenderInterface: An instance of EmailSender configured with the appropriate email settings.
    """
    return EmailSender(
        hostname=settings.EMAIL_HOST,
        port=settings.EMAIL_PORT,
        email=settings.EMAIL_HOST_USER,
        password=settings.EMAIL_HOST_PASSWORD,
        use_tls=settings.EMAIL_USE_TLS,
        template_dir=settings.PATH_TO_EMAIL_TEMPLATES_DIR,
        # For accounts
        activation_email_template_name=settings.ACTIVATION_EMAIL_TEMPLATE_NAME,
        activation_complete_email_template_name=settings.ACTIVATION_COMPLETE_EMAIL_TEMPLATE_NAME,
        password_email_template_name=settings.PASSWORD_RESET_TEMPLATE_NAME,
        password_complete_email_template_name=settings.PASSWORD_RESET_COMPLETE_TEMPLATE_NAME,
        password_change_email_template_name=settings.PASSWORD_CHANGE_NAME,
        # For payments
        send_payment_email_template_name=settings.SEND_PAYMENT_EMAIL_TEMPLATE_NAME,
        send_refund_email_template_name=settings.SEND_REFUND_EMAIL_TEMPLATE_NAME,
        send_cancellation_email_template_name=settings.SEND_CANCELLATION_EMAIL_TEMPLATE_NAME,
    )


async def get_current_user_id(
    token: str = Depends(get_token),
    jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> int:
    """
    Extracts the user ID from the provided JWT token.
    """
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = int(payload.get("user_id"))
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: user_id missing",
            )
        return user_id
    except BaseSecurityError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
