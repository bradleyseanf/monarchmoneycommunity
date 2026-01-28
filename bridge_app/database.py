import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv(override=True)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./bridge.db")

connect_args = {}
import urllib.parse

# Fix driver and sslmode for asyncpg
if DATABASE_URL.startswith("postgresql"):
    # Ensure correct driver
    if DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    
    # Parse query params robustly
    parsed = urllib.parse.urlparse(DATABASE_URL)
    query_params = urllib.parse.parse_qs(parsed.query)
    
    # Check for SSL requirements in query
    # asyncpg prefers these in connect_args, not URL params usually
    if "sslmode" in query_params or "channel_binding" in query_params:
        # Strip them from the URL
        new_query = urllib.parse.urlencode({
            k: v for k, v in query_params.items() 
            if k not in ['sslmode', 'channel_binding']
        }, doseq=True)
        
        DATABASE_URL = urllib.parse.urlunparse(parsed._replace(query=new_query))
        
        # Enforce SSL for Neon/Cloud Postgres
        # asyncpg requires True or an SSLContext, not string "require"
        connect_args = {"ssl": True}

engine = create_async_engine(DATABASE_URL, echo=True, connect_args=connect_args)

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
