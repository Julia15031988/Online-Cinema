from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models.orders import Order, OrderItem
from src.database.models.user import User
from src.database.models.cart import Cart, CartItem
from src.database.models.movies import Movie
from src.schemas.cart import CartResponse, CartItemSchema
from fastapi import APIRouter, Depends, HTTPException, status
from src.database.session import get_db
from src.config.dependencies import get_current_user


router = APIRouter()


@router.get(
    "/",
    response_model=CartResponse,
    summary="Get the current user's cart",
    description="Retrieve the shopping cart of "
    "the authenticated user, including all "
    "added movies.",
    status_code=status.HTTP_200_OK,
)
async def get_cart_by_user_id(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
) -> CartResponse:
    stmt = select(Cart).where(Cart.user_id == current_user.id)
    result = await db.execute(stmt)
    cart = result.scalar_one_or_none()

    if not cart:
        raise HTTPException(
            status_code=404,
            detail=f"No cart found for user with ID '{current_user.id}'.",
        )

    movies_list = []

    for item in cart.items:
        movie_data = CartItemSchema(
            movie_id=item.movie.id,
            name=item.movie.name,
            price=float(item.movie.price),
            added_at=item.added_at,
        )
        movies_list.append(movie_data)

    return CartResponse(
        user_id=current_user.id,
        movies=movies_list,
    )


@router.post(
    "/",
    summary="Add a movie to the cart",
    description="Add a selected movie to the " "authenticated user's shopping cart.",
    status_code=status.HTTP_201_CREATED,
)
async def add_cart_item(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt_movie = select(Movie).where(Movie.id == movie_id)
    result = await db.execute(stmt_movie)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Movie with ID '{movie_id}' not found.",
        )

    stmt_cart = select(Cart).where(Cart.user_id == current_user.id)
    result = await db.execute(stmt_cart)
    cart = result.scalars().first()

    if not cart:
        cart = Cart(user_id=current_user.id)
        db.add(cart)
        await db.commit()
        await db.refresh(cart)

    if any(item.movie_id == movie_id for item in cart.items):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This movie is already present in your cart.",
        )

    stmt_purchase = (
        select(OrderItem)
        .join(Order)
        .where(
            OrderItem.movie_id == movie_id,
            Order.user_id == current_user.id,
        )
    )
    result = await db.execute(stmt_purchase)
    purchase = result.scalars().first()

    if purchase:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already purchased this movie. "
            "Repeat purchases are not allowed.",
        )

    cart_item = CartItem(
        cart_id=cart.id,
        movie_id=movie_id,
    )

    db.add(cart_item)
    await db.commit()
    await db.refresh(cart_item)

    return {"detail": "Movie added to the cart successfully"}


@router.delete(
    "/{movie_id}",
    summary="Remove a movie from the cart",
    description="Removes a movie from the authenticated user's cart",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_movie_from_cart(
    movie_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt_cart = select(Cart).where(Cart.user_id == current_user.id)
    result = await db.execute(stmt_cart)
    cart = result.scalars().first()

    if not cart:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart not found for the current user.",
        )

    stmt_movie = select(CartItem).where(
        CartItem.cart_id == cart.id, CartItem.movie_id == movie_id
    )
    result = await db.execute(stmt_movie)
    movie = result.scalars().first()

    if not movie:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Movie with ID {movie_id} was not found in your cart.",
        )

    await db.delete(movie)
    await db.commit()

    return
