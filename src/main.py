from fastapi import FastAPI
from sqlalchemy import select, insert
from src.routes import (
    auth_router,
    movies_router,
    cart_router,
    orders_router,
    payments_router,
)
from src.database.models.user import UserGroup, UserGroupEnum
from src.database.session import engine
from src.database.models.base import Base


app = FastAPI(
    title="Online cinema",
    version="1.0",
    description="API for managing movies, users, and orders in an online cinema.",
)


async def ensure_default_group():
    async with engine.begin() as conn:
        existing = await conn.execute(select(UserGroup.name))
        existing_names = {row[0] for row in existing.fetchall()}
        required = {
            UserGroupEnum.USER,
            UserGroupEnum.ADMIN,
            UserGroupEnum.MODERATOR,
        }
        missing = required - existing_names

        if missing:
            await conn.execute(
                insert(UserGroup),
                [{"name": name} for name in missing],
            )


@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_default_group()


api_version_prefix = "/api/v1"

app.include_router(auth_router, prefix=f"{api_version_prefix}/accounts", tags=["accounts"])
app.include_router(movies_router, prefix=f"{api_version_prefix}/movies", tags=["movies"])
app.include_router(cart_router, prefix=f"{api_version_prefix}/cart", tags=["cart"])
app.include_router(orders_router, prefix=f"{api_version_prefix}/order", tags=["orders"])
app.include_router(payments_router, prefix=f"{api_version_prefix}/payment", tags=["payments"])