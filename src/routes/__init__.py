from .auth import auth_router
from .movies import movies_router
from .cart import cart_router
from .orders import orders_router
from .payments import payments_router

__all__ = [ "auth_router", "movies_router", "cart_router", "orders_router", "payments_router", ]