"""Villanyan-Agent 3.0 — Cost routes (LLM cost rates)."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.db import get_db
from backend.core.models import CostRate, User
from backend.core.security import get_current_user

router = APIRouter(prefix="/api/costs", tags=["costs"])


@router.get("")
async def list_costs(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all configured LLM cost rates."""
    result = await db.execute(select(CostRate).order_by(CostRate.model))
    rates = result.scalars().all()

    return {
        "items": [
            {
                "id": r.id,
                "model": r.model,
                "price_in": r.price_in,
                "price_out": r.price_out,
                "currency": r.currency,
                "updated_at": r.updated_at.isoformat(),
            }
            for r in rates
        ],
        "total": len(rates),
    }
