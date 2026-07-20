from sqlalchemy.orm import Session
from app.db.models import UrlMapping
from sqlalchemy.dialects.postgresql import insert

class UrlRepository:
    def __init__(self, db: Session):
        self.db = db

    def find_by_short_code(self, short_code: str) -> UrlMapping | None:
        return (
            self.db.query(UrlMapping)
            .filter(UrlMapping.short_code == short_code)
            .first()
        )
    
    
    def find_and_store_short_code(self, original_url: str, short_code: str, alias: str | None, expiration_time = None) -> UrlMapping:
        
        insert_stmt = insert(UrlMapping).values(original_url=original_url, 
                                             short_code=short_code, 
                                             alias=alias, 
                                             expiration_time=expiration_time)
        stmt = insert_stmt.on_conflict_do_nothing(index_elements=["short_code"])
        self.db.execute(stmt)
        self.db.commit()
        
        return self.find_by_short_code(short_code)
        
    def update_mapping(self, mapping: UrlMapping, original_url: str, expiration_time=None) -> UrlMapping:
        mapping.original_url = original_url
        mapping.expiration_time = expiration_time
        self.db.commit()
        self.db.refresh(mapping)
        return mapping

    
