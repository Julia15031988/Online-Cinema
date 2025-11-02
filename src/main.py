from fastapi import FastAPI
from src.routes.auth import router as auth_router
from src.routes.movies import router as movie_router
from src.routes.cart import router as cart_router
from src.routes.orders import router as orders_router
from src.config.settings import settings
from src.database.models.base import Base
from src.database.session import engine
app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Welcome to Online Cinema!"}


app.include_router(auth_router)
app.include_router(movie_router)
app.include_router(cart_router)

app.include_router(orders_router)