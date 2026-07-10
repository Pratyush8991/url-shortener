from sqlalchemy.orm import Session
from app.db.models import UrlMapping

class UrlRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_by_short_code(self, short_code: str) -> UrlMapping | None:
        return (
            self.db.query(UrlMapping)
            .filter(UrlMapping.short_code == short_code)
            .first()
        )
    
    def find_by_alias(self, alias: str) -> UrlMapping | None:
        return(
            self.db.query(UrlMapping)
            .filter(UrlMapping.alias == alias)
            .first()
        )
    
    def store_short_code(self, original_url: str, short_code: str, 
                         alias: str | None, expiration_time=None) ->UrlMapping:
        mapping = UrlMapping(original_url=original_url,
                             short_code=short_code,
                             alias=alias,
                             expiration_time=expiration_time)
        
        self.db.add(mapping)
        self.db.commit()
        self.db.refresh(mapping)
        return mapping

    def reactivate_mapping(self, mapping: UrlMapping, expiration_time=None) -> UrlMapping:
        mapping.expiration_time = expiration_time
        self.db.commit()
        self.db.refresh(mapping)
        return mapping

    def reassign_expired_alias(self,
                                mapping: UrlMapping,
                                original_url: str,
                                expiration_time=None,
                            ) -> UrlMapping:
        mapping.original_url = original_url
        mapping.expiration_time = expiration_time
        self.db.commit()
        self.db.refresh(mapping)
        return mapping
    
