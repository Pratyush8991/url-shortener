from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.dependencies import get_db
from app.repositories.url_repo import UrlRepository
from app.services.redirect_service import RedirectService
from app.services.url_service import URLService
from app.strategies.hash_strategy import HashUrlCreationStrategy

def get_url_creation_strategy():
    return HashUrlCreationStrategy()


def get_url_repository(db: Annotated[Session, Depends(get_db)]) -> UrlRepository:
    return UrlRepository(db)


def get_url_service(repo: Annotated[UrlRepository, Depends(get_url_repository)], url_creation_strategy=Depends(get_url_creation_strategy)) -> URLService:
    settings = get_settings()
    return URLService(repo, url_creation_strategy, settings.public_base_url)


def get_redirect_service(repo: Annotated[UrlRepository, Depends(get_url_repository)]) -> RedirectService:
    return RedirectService(repo)
