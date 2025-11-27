from datetime import datetime, timezone

from src.database.session import async_session
from src.database.models.user import (
    RefreshToken,
    ActivationToken,
    PasswordResetToken
)
from src.celery_app.celery_app import celery_app
import asyncio


def delete_expired_token_sync():
    async def inner():
        async with async_session() as db:
            now_utc = datetime.now(timezone.utc)

            await db.execute(
                RefreshToken.__table__.delete().where(
                    RefreshToken.expires_at < now_utc
                )
            )

            await db.execute(
                ActivationToken.__table__.delete().where(
                    ActivationToken.expires_at < now_utc
                )
            )

            await db.execute(
                PasswordResetToken.__table__.delete().where(
                    PasswordResetToken.expires_at < now_utc
                )
            )

            await db.commit()
    asyncio.run(inner())


@celery_app.task
def delete_expired_token_task():
    delete_expired_token_sync()