import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

logger = logging.getLogger("payrecover.db")

Base = declarative_base()

# Determine DB Engine with resilient fallback
engine = None

# Attempt PostgreSQL first if explicitly configured or configured in standard DATABASE_URL
db_url = settings.DATABASE_URL

try:
    if db_url.startswith("sqlite"):
        engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            echo=False
        )
        logger.info(f"Connected to SQLite Database: {db_url}")
    else:
        # Try connecting to PostgreSQL
        test_engine = create_engine(db_url, pool_pre_ping=True)
        with test_engine.connect() as conn:
            pass
        engine = test_engine
        logger.info(f"Connected to PostgreSQL Database: {db_url.split('@')[-1] if '@' in db_url else db_url}")
except Exception as e:
    logger.warning(f"Could not connect to target DB ({db_url}): {e}. Falling back to local SQLite.")
    sqlite_url = "sqlite:///./payrecover.db"
    engine = create_engine(
        sqlite_url,
        connect_args={"check_same_thread": False},
        echo=False
    )
    logger.info(f"Fallback to SQLite database: {sqlite_url}")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
