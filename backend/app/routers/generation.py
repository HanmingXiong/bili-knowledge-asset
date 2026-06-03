from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import AssetQueryResponse, GenerateRequest, GenerateResponse, MultiAssetQueryRequest
from app.services.extraction import generate_from_assets, query_assets

router = APIRouter()


@router.post("/generate", response_model=GenerateResponse)
def generate(payload: GenerateRequest, db: Session = Depends(get_db)) -> GenerateResponse:
    try:
        output = generate_from_assets(payload.asset_ids, payload.output_type, payload.user_prompt, db)
        return GenerateResponse(output=output)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Generation failed: {exc}") from exc


@router.post("/query", response_model=AssetQueryResponse)
def query_multiple_assets(payload: MultiAssetQueryRequest, db: Session = Depends(get_db)) -> AssetQueryResponse:
    try:
        return query_assets(payload.asset_ids, payload.question, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Multi-asset query failed: {exc}") from exc
