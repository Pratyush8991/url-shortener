"""
1. Create shortUrl from originalUrl
2. Check DB for shortUrl
3. If shortUrl not in DB, store in DB.
4. Return to user.
5. If shortUrl in DB, return the shortUrl to user.
6. If alias provided, check DB for alias first.
"""

from datetime import datetime

from pydantic import HttpUrl
from app.exceptions import AliasAlreadyExistsError, ShortCodeExhaustionError
from app.repositories.url_repo import UrlRepository
from app.config import ATTEMPT_CAP

class URLService:
    def __init__(self, repo: UrlRepository, url_creation_strategy, public_base_url: str):
        self.repo = repo
        self.url_strategy = url_creation_strategy
        self.public_base_url = public_base_url.rstrip("/")
    
    # Create
    def create_short_url(self, originalUrl: HttpUrl, alias: str = None, expirationTime: datetime | None = None) -> str:
        original_url = self.parse_url(originalUrl)
        
        if not alias:
            attempt = 0
            while attempt <= ATTEMPT_CAP:
                code = self.url_strategy.create_short_code(original_url, attempt)
                short_url = f"{self.public_base_url}/{code}"

                # Instead of splitting the find then insert,
                # turn it into one transaction - UPSERT.
                # Update or Insert - on conflict, do nothing.
                
                mapping = self.repo.find_and_store_short_code(original_url, code, alias, expirationTime)

                if mapping.original_url == original_url:
                    if expirationTime != mapping.expiration_time:
                        self.repo.update_mapping(mapping=mapping, original_url=original_url, expiration_time=expirationTime)
                
                    return short_url
                # Hash collision case - a short code mapped to two different original URLs.
                else:
                    attempt += 1


            raise ShortCodeExhaustionError(original_url)

        else:
            short_url = f"{self.public_base_url}/{alias}"

            alias_mapping = self.repo.find_and_store_short_code(original_url=original_url, short_code=alias, alias=alias, expiration_time=expirationTime)
            
            if alias_mapping.original_url != original_url and not self.is_expired(alias_mapping):
                raise AliasAlreadyExistsError(alias)

            # Skip the write on a fresh insert (nothing changed); only write on a
            # same-owner expiration change or an expired-alias reclaim.
            if alias_mapping.original_url != original_url or expirationTime != alias_mapping.expiration_time:
                self.repo.update_mapping(mapping=alias_mapping, original_url=original_url, expiration_time=expirationTime)
            return short_url

    def parse_url(self, url: HttpUrl) -> str:
        return str(url)
    
    def is_expired(self, mapping):
        if not mapping.expiration_time:
            return False
        now = datetime.now(mapping.expiration_time.tzinfo)
        if mapping.expiration_time <= now:
            return True
        return False

    
