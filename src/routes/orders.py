from typing import List, Optional
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.session import get_db
from src.database.models.user import User
from src.database.models.cart import Cart
from src.database.models.orders import Order, OrderItem, OrderStatusEnum
from src.schemas.orders import (
    OrderResponseSchema,
    OrderMovieSchema,
    OrderListItemSchema,
    OrderListResponseSchema,
)
from src.security.auth_dependencies import get_current_user, admin_required

router = APIRouter()


@router.post(
    "/",
    response_model=OrderResponseSchema,
    summary="Create an order from the cart",
    description="Creates a new order for all movies in the authenticated user's cart",
    status_code=status.HTTP_201_CREATED,
)
async def create_order(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OrderResponseSchema:
    stmt_cart = select(Cart).where(Cart.user_id == current_user.id)
    result = await db.execute(stmt_cart)
    cart = result.scalar_one_or_none()

    if not cart or not cart.items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart is empty or not found",
        )

    cart_items = list(cart.items)

    for item in cart.items:
        if not item.movie:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Movie with id {item.movie_id} no longer exists",
            )

        stmt_bought = (
            select(OrderItem)
            .join(Order)
            .where(
                Order.user_id == current_user.id,
                Order.status == OrderStatusEnum.Paid,
                Order.movie_id == item.movie_id,
            )
        )
        result = await db.execute(stmt_bought)
        if result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Movie '{item.movie.name}' already purchased",
            )

        stmt_pending = (
            select(OrderItem)
            .join(Order)
            .where(
                Order.user_id == current_user.id,
                Order.status == OrderStatusEnum.Pending,
                OrderItem.movie_id == item.movie_id,
            )
        )
        result = await db.execute(stmt_pending)
        if result.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Movie '{item.movie.name}' is already in a pending order",
            )

    total_amount = sum(item.movie.price for item in cart.items)

    new_order = Order(user_id=current_user.id, total_amount=total_amount)
    db.add(new_order)

    for item in cart_items:
        db.add(
            OrderItem(
                order=new_order, movie_id=item.movie_id, price_at_order=item.movie.price
            )
        )

    for item in cart_items:
        await db.delete(item)

    await db.commit()
    await db.refresh(new_order)

    items = [
        OrderMovieSchema(
            movie_id=item.movie_id,
            name=item.movie.name,
            price_at_order=item.movie.price,
        )
        for item in cart_items
    ]

    return OrderResponseSchema(
        id=new_order.id,
        user_id=new_order.user_id,
        created_at=new_order.created_at,
        status=new_order.status.value,
        total_amount=total_amount,
        items=items,
    )


@router.post(
    "/{order_id}/pay",
    summary="Pay for an order",
    description="Processes payment for a specific order of the current user.",
    status_code=status.HTTP_200_OK,
)
async def pay_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt_order = select(Order).where(
        Order.id == order_id,
        Order.user_id == current_user.id,
    )
    result = await db.execute(stmt_order)
    order = result.scalars().first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with ID '{order_id}' not found.",
        )

    if order.status == OrderStatusEnum.Paid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order '{order.id}' has already been paid.",
        )

    order.status = OrderStatusEnum.Paid
    await db.commit()
    await db.refresh(order)

    return {"message": f"Order {order.id} has been successfully paid."}


@router.post(
    "/{order_id}/cancel",
    summary="Cancel a pending order",
    description="Allows a user to cancel their order if it has not been paid yet.",
    status_code=status.HTTP_200_OK,
)
async def cancel_order(
    order_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt_order = select(Order).where(
        Order.id == order_id,
        Order.user_id == current_user.id,
    )
    result = await db.execute(stmt_order)
    order = result.scalars().first()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with ID '{order_id}' not found.",
        )

    if order.status == OrderStatusEnum.Cancelled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order '{order.id}' is already canceled.",
        )

    if order.status == OrderStatusEnum.Paid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Paid orders cannot be canceled directly",
        )

    order.status = OrderStatusEnum.Cancelled
    await db.commit()
    await db.refresh(order)

    return {"detail": f"Order '{order.id}' has been successfully canceled."}


@router.get(
    "/admin/",
    response_model=List[OrderResponseSchema],
    summary="View all user orders (admin)",
    description="Allows admins to view all user orders with filters.",
    status_code=status.HTTP_200_OK,
)
async def get_orders_for_admin(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(admin_required),
    user_id: Optional[int] = Query(None, description="Filter by user id"),
    start_date: Optional[date] = Query(None, description="Filter by start date"),
    end_date: Optional[date] = Query(None, description="Filter by end date"),
    order_status: Optional[OrderStatusEnum] = Query(
        None, description="Filter by order status"
    ),
) -> List[OrderResponseSchema]:
    stmt = select(Order)

    if user_id is not None:
        stmt = stmt.where(Order.user_id == user_id)
    if start_date is not None:
        stmt = stmt.where(Order.created_at >= start_date)
    if end_date is not None:
        stmt = stmt.where(Order.created_at <= end_date)
    if order_status is not None:
        stmt = stmt.where(Order.status == order_status)

    result = await db.execute(stmt)
    orders = result.scalars().all()

    if not orders:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No orders found matching the specified filters.",
        )

    order_list = []
    for order in orders:
        items = [
            OrderMovieSchema(
                movie_id=item.movie_id,
                name=item.movie.name,
                price_at_order=item.price_at_order,
            )
            for item in order.items
        ]

        order_response = OrderResponseSchema(
            id=order.id,
            user_id=order.user_id,
            created_at=order.created_at,
            status=order.status.value,
            total_amount=order.total_amount,
            items=items,
        )
        order_list.append(order_response)

    return order_list
