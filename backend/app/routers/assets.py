from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import (
    AssetCreateRequest,
    AssetDetailResponse,
    AssetQueryRequest,
    AssetQueryResponse,
    AssetRetryRequest,
    AssetRetryResponse,
    AssetSummaryResponse,
)
from app.services.extraction import (
    create_or_get_asset,
    ensure_asset_indexed,
    get_asset_by_id,
    list_assets as list_assets_query,
    query_asset,
    retry_asset,
    serialize_asset_detail,
    serialize_asset_summary,
)

router = APIRouter()


@router.post("/create", response_model=AssetDetailResponse)
def create_asset(payload: AssetCreateRequest, db: Session = Depends(get_db)) -> AssetDetailResponse:
    try:
        asset = create_or_get_asset(payload.source_url, db)
        return serialize_asset_detail(asset, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Asset creation failed: {exc}") from exc


@router.get("", response_model=list[AssetSummaryResponse])
def list_assets(db: Session = Depends(get_db)) -> list[AssetSummaryResponse]:
    return [serialize_asset_summary(asset) for asset in list_assets_query(db)]


@router.get("/{asset_id}", response_model=AssetDetailResponse)
def get_asset(asset_id: int, db: Session = Depends(get_db)) -> AssetDetailResponse:
    asset = get_asset_by_id(asset_id, db)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    asset = ensure_asset_indexed(asset, db)
    return serialize_asset_detail(asset, db)


@router.post("/{asset_id}/query", response_model=AssetQueryResponse)
def ask_asset(asset_id: int, payload: AssetQueryRequest, db: Session = Depends(get_db)) -> AssetQueryResponse:
    try:
        return query_asset(asset_id, payload.question, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Asset query failed: {exc}") from exc


@router.post("/{asset_id}/retry", response_model=AssetRetryResponse)
def retry_asset_extraction(
    asset_id: int, payload: AssetRetryRequest, db: Session = Depends(get_db)
) -> AssetRetryResponse:
    try:
        return retry_asset(asset_id, payload.stage, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Asset retry failed: {exc}") from exc
