import stripe
from typing import Optional, List
from datetime import date
from decimal import Decimal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Request,
    Query,
    BackgroundTasks,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.session import get_db
from src.config.settings import settings
from src.config.email_utils import get_accounts_email_notificator
from src.notifications.interfaces import EmailSenderInterface
from src.database.models.user import User
from src.database.models.orders import Order, OrderItem, OrderStatusEnum
from src.database.models.payments import Payment, PaymentItem, PaymentStatusEnum


from src.schemas.payments import (
    PaymentCreate,
    PaymentResponse,
    PaymentItemResponse,
)

from src.security.auth_dependencies import get_current_user, admin_required

router = APIRouter()

stripe.api_key = settings.STRIPE_SECRET_KEY
stripe.webhook_secret = settings.STRIPE_WEBHOOK_SECRET


async def update_payment_status(
        db: AsyncSession,
        status: PaymentStatusEnum,
        external_id: str,
):
    stmt = select(Payment).where(Payment.external_payment_id == external_id)
    result = await db.execute(stmt)
    payment = result.scalars().first()

    if payment:
        payment.status = status
        await db.commit()


@router.post(
    "/",
    response_model=PaymentResponse,
    summary="Create a payment",
    description="Processes a payment for a user's order via Stripe.",
    status_code=status.HTTP_201_CREATED,
)
async def create_payment(
        payment_data: PaymentCreate,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
) -> PaymentResponse:
    stmt_order = select(Order).where(
        Order.id == payment_data.order_id,
        Order.user_id == current_user.id,
    )
    result = await db.execute(stmt_order)
    order = result.scalars().first()

    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.status == OrderStatusEnum.Paid:
        raise HTTPException(status_code=400, detail="Order already paid")

    stmt_items = select(OrderItem).where(OrderItem.order_id == payment_data.order_id)
    result = await db.execute(stmt_items)
    items = result.scalars().all()

    total_amount = sum(item.price_at_order for item in items)

    if not stripe.api_key:
        raise HTTPException(
            status_code=503,
            detail="Payment service not configured. Please try later.",
        )

    try:
        intent = stripe.PaymentIntent.create(
            amount=int((total_amount * Decimal(100)).to_integral_value()),
            currency="uah",
            payment_method_types=["card"],
        )
    except stripe.InvalidRequestError:
        raise HTTPException(status_code=400, detail="Invalid payment method")
    except stripe.StripeError:
        raise HTTPException(status_code=502, detail="Payment processing error")

    payment = Payment(
        user_id=current_user.id,
        order_id=order.id,
        amount=total_amount,
        external_payment_id=intent.id,
        status=PaymentStatusEnum.Successful,
    )

    payment.items = [
        PaymentItem(
            order_item_id=item.id,
            price_at_payment=item.price_at_order,
        )
        for item in items
    ]

    db.add(payment)
    await db.commit()
    await db.refresh(payment)

    return PaymentResponse(
        id=payment.id,
        user_id=payment.user_id,
        order_id=payment.order_id,
        created_at=payment.created_at,
        status=payment.status,
        amount=payment.amount,
        external_payment_id=payment.external_payment_id,
        payment_method="card",
        client_secret=intent.client_secret,
        payment_items=[
            PaymentItemResponse(
                id=pi.id,
                payment_id=pi.payment_id,
                order_item_id=pi.order_item_id,
                price_at_payment=pi.price_at_payment,
            )
            for pi in payment.items
        ],
    )


@router.post(
    "/webhook",
    summary="Stripe Webhook",
    description="Receives Stripe events and updates payment status.",
    status_code=status.HTTP_200_OK,
)
async def stripe_webhook(
        request: Request,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db),
        email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
):
    payload = await request.body()
    sig_head = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_head, stripe.webhook_secret)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "payment_intent.succeeded":
        await update_payment_status(db, PaymentStatusEnum.Successful, event["data"]["object"]["id"])
        stmt = select(Payment).where(Payment.external_payment_id == event["data"]["object"]["id"])
        result = await db.execute(stmt)
        payment = result.scalars().first()

        if payment:
            order_link = f"https://localhost:8000/api/v1/payment/{payment.order_id}"
            background_tasks.add_task(
                email_sender.send_success_payment,
                payment.user.email,
                order_link,
            )

    elif event["type"] == "payment_intent.payment_failed":
        await update_payment_status(db, PaymentStatusEnum.Canceled, event["data"]["object"]["id"])

    elif event["type"] == "charge.refunded":
        await update_payment_status(db, PaymentStatusEnum.Refunded, event["data"]["object"]["id"])

    return {"status": "success"}


@router.get(
    "/",
    response_model=List[PaymentResponse],
    summary="Get user's payments",
    description="Returns all payments of the current user with optional filters.",
    status_code=status.HTTP_200_OK,
)
async def get_payments_by_user(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
        pay_status: Optional[PaymentStatusEnum] = Query(None, description="Filter by status"),
        start_date: Optional[date] = Query(None, description="Filter by start date"),
        end_date: Optional[date] = Query(None, description="Filter by end date"),
) -> List[PaymentResponse]:
    stmt = select(Payment).where(Payment.user_id == current_user.id)

    if pay_status is not None:
        stmt = stmt.where(Payment.status == pay_status)
    if start_date is not None:
        stmt = stmt.where(Payment.created_at >= start_date)
    if end_date is not None:
        stmt = stmt.where(Payment.created_at <= end_date)

    result = await db.execute(stmt)
    payments = result.scalars().all()

    if not payments:
        raise HTTPException(status_code=404, detail="No payments found")

    return [
        PaymentResponse(
            id=p.id,
            user_id=p.user_id,
            order_id=p.order_id,
            created_at=p.created_at,
            status=p.status,
            amount=p.amount,
            external_payment_id=p.external_payment_id,
            payment_method="card",
            client_secret=None,
            payment_items=[
                PaymentItemResponse(
                    id=pi.id,
                    payment_id=pi.payment_id,
                    order_item_id=pi.order_item_id,
                    price_at_payment=pi.price_at_payment,
                )
                for pi in p.items
            ],
        )
        for p in payments
    ]


@router.get(
    "/admin/",
    response_model=List[PaymentResponse],
    summary="View all user payments (admin)",
    description="Allows admins to view all user payments with filters.",
    status_code=status.HTTP_200_OK,
)
async def get_payments_by_admin(
        db: AsyncSession = Depends(get_db),
        admin_user: User = Depends(admin_required),
        user_id: Optional[int] = Query(None, description="Filter by user id"),
        pay_status: Optional[PaymentStatusEnum] = Query(None, description="Filter by status"),
        start_date: Optional[date] = Query(None, description="Filter by start date"),
        end_date: Optional[date] = Query(None, description="Filter by end date"),
) -> List[PaymentResponse]:
    stmt = select(Payment)

    if user_id is not None:
        stmt = stmt.where(Payment.user_id == user_id)
    if pay_status is not None:
        stmt = stmt.where(Payment.status == pay_status)
    if start_date is not None:
        stmt = stmt.where(Payment.created_at >= start_date)
    if end_date is not None:
        stmt = stmt.where(Payment.created_at <= end_date)

    result = await db.execute(stmt)
    payments = result.scalars().all()

    if not payments:
        raise HTTPException(status_code=404, detail="No payments found")
    return payments
