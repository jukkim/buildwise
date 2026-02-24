"""AI routes — natural language building generation."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db import get_db
from app.models.user import User
from app.schemas.api import NLParseRequest, NLParseResponse
from app.services.ai.nl_parser import parse_building_from_text

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/parse-building", response_model=NLParseResponse)
async def parse_building(
    body: NLParseRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NLParseResponse:
    """POST /api/v1/ai/parse-building — 자연어 → BPS JSON 변환."""
    try:
        result = await parse_building_from_text(body.text)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    except Exception:
        logger.exception("AI parsing failed for input: %s", body.text[:100])
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service temporarily unavailable. Please use template selection instead.",
        )

    return NLParseResponse(
        name=result.name,
        building_type=result.building_type,
        bps=result.bps,
        confidence=result.confidence,
        extracted_params=result.extracted_params,
        default_params=result.default_params,
        warnings=result.warnings,
    )
