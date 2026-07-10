from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from app.services.redirect_service import RedirectService
from app.dependencies import get_redirect_service
from app.exceptions import UrlNotFoundError, UrlExpiredError

router = APIRouter()

@router.get("/{shortCode}")
def redirect_to_original_url(shortCode: str, redirects: Annotated[RedirectService, Depends(get_redirect_service)]):
    try:
        originalUrl = redirects.get_original_url(shortCode)
    except UrlNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except UrlExpiredError as exc:
        raise HTTPException(status_code=410, detail=str(exc))


    return RedirectResponse(originalUrl, status_code=302)
