from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from app.exceptions import AliasAlreadyExistsError, ShortCodeExhaustionError
from app.models.urls import CreateUrlRequest
from app.services.url_service import URLService
from app.dependencies import get_url_service

router = APIRouter()

@router.post("/urls", response_model=None, status_code=200)
def create_url(payload: CreateUrlRequest, url_creation_service: Annotated[URLService, Depends(get_url_service)]):
    try:
        short_url = url_creation_service.create_short_url(payload.originalUrl, payload.alias, payload.expirationTime)
    except AliasAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ShortCodeExhaustionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not short_url:
        raise HTTPException(status_code=400, detail="Unable to create short URL")
    return short_url
