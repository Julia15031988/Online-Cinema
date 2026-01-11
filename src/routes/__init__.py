from .auth import router as auth_router
from .movies import router as movies_router
from .cart import router as cart_router
from .orders import router as orders_router
from .payments import router as payments_router

__all__ = [
    "auth_router",
    "movies_router",
    "cart_router",
    "orders_router",
    "payments_router",
]
