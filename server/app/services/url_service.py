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
from app.exceptions import AliasAlreadyExistsError
from app.repositories.url_repo import UrlRepository

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
            while True:
                code = self.url_strategy.create_short_code(original_url, attempt)
                mapping = self.repo.find_by_short_code(code)
                short_url = f"{self.public_base_url}/{code}"

                if mapping is None:
                    self.repo.store_short_code(original_url, code, alias, expirationTime)
                    return short_url

                if mapping.original_url == original_url:
                    if expirationTime != mapping.expiration_time:
                        self.repo.update_expiration(mapping, expirationTime)
                    
                    return short_url
                
                attempt += 1

                
        else:
            short_url = f"{self.public_base_url}/{alias}"
            alias_mapping = self.repo.find_by_alias(alias)
            
            if not alias_mapping:
                self.repo.store_short_code(original_url, alias, alias, expirationTime)
                return short_url
            
            if not self.is_expired(alias_mapping):
                raise AliasAlreadyExistsError(alias)

            self.repo.reassign_expired_alias(alias_mapping, original_url, expirationTime)
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

    
