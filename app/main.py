from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import oauth
from app.auth.router import router as auth_router
from app.db.models import OAuthToken
from app.db.session import get_session, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Back-Office Agent", lifespan=lifespan)
app.include_router(auth_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def index(db: Session = Depends(get_session)):
    connected = [row.provider for row in db.execute(select(OAuthToken)).scalars()]
    return {
        "connected": connected,
        "connect_urls": {p: f"/auth/{p}/login" for p in oauth.provider_names()},
    }
