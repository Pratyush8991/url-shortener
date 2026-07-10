"""
1. When user clicks on short url, it should call redirect_service.py
2. Check DB if url is present and not expired
3. return original url or None
"""
from datetime import datetime
from app.repositories.url_repo import UrlRepository
from app.exceptions import UrlNotFoundError, UrlExpiredError

class RedirectService:
    def __init__(self, repo: UrlRepository):
        self.repo = repo

    def get_original_url(self, shortCode):
        mapping = self.repo.find_by_short_code(shortCode)
        if not mapping:
            raise UrlNotFoundError(shortCode)
        
        if self.is_expired(mapping):
            raise UrlExpiredError(shortCode)
        
        return mapping.original_url
    
    def is_expired(self, mapping):
        if not mapping.expiration_time:
            return False
        now = datetime.now(mapping.expiration_time.tzinfo)
        if mapping.expiration_time <= now:
            return True
        return False

            
