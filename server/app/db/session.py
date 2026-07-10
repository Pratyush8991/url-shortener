from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import get_settings

DATABASE_URL = get_settings().database_url

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)