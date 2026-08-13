from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import oauth
from app.auth.tokens import save_token
from app.db.models import AuditLog
from app.db.session import get_session

router = APIRouter(prefix="/auth", tags=["auth"])

# Maps OAuth `state` -> (provider, pkce_verifier). In-memory is fine for a
# single-user dev tool; move to the DB/redis when multi-user or restart-safe.
_PENDING: dict[str, tuple[str, str | None]] = {}


@router.get("/{provider}/login")
def login(provider: str):
    try:
        p = oauth.get_provider(provider)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown provider")
    if not p.client_id:
        raise HTTPException(
            status_code=400,
            detail=f"{provider} is not configured — set its credentials in .env",
        )

    state = secrets.token_urlsafe(24)
    verifier = challenge = None
    if p.use_pkce:
        verifier, challenge = oauth.make_pkce()
    _PENDING[state] = (provider, verifier)

    return RedirectResponse(oauth.build_authorize_url(p, state, challenge))


@router.get("/{provider}/callback")
def callback(provider: str, request: Request, db: Session = Depends(get_session)):
    params = request.query_params
    if params.get("error"):
        raise HTTPException(status_code=400, detail=f"Authorization error: {params['error']}")

    code = params.get("code")
    state = params.get("state")
    if not code or not state or state not in _PENDING:
        raise HTTPException(status_code=400, detail="Missing or invalid code/state")

    saved_provider, verifier = _PENDING.pop(state)
    if saved_provider != provider:
        raise HTTPException(status_code=400, detail="Provider mismatch")

    p = oauth.get_provider(provider)
    token = oauth.exchange_code(p, code, verifier)

    extra = None
    if provider == "xero":
        extra = {"tenant_id": oauth.fetch_xero_tenant(token["access_token"])}

    save_token(db, provider, token, extra=extra)
    db.add(AuditLog(action="oauth_connected", detail={"provider": provider}))
    db.commit()

    return {"connected": provider, "extra": extra or {}}
