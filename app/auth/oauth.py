"""Unified OAuth 2.0 auth-code helper for all self-hosted integrations.

One generic client drives every provider; per-provider differences (PKCE,
token-endpoint auth style, extra authorize params) live in ProviderConfig.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass, field
from urllib.parse import urlencode

import httpx

from app.config import get_settings


@dataclass
class ProviderConfig:
    name: str
    authorize_url: str
    token_url: str
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: list[str]
    use_pkce: bool = False
    token_auth: str = "basic"  # "basic" (HTTP Basic) or "body" (client_id in body)
    scope_separator: str = " "
    extra_authorize_params: dict = field(default_factory=dict)


def _providers() -> dict[str, ProviderConfig]:
    s = get_settings()
    return {
        "xero": ProviderConfig(
            name="xero",
            authorize_url="https://login.xero.com/identity/connect/authorize",
            token_url="https://identity.xero.com/connect/token",
            client_id=s.xero_client_id,
            client_secret=s.xero_client_secret,
            redirect_uri=s.xero_redirect_uri,
            scopes=[
                "offline_access",
                "openid",
                "profile",
                "email",
                "accounting.transactions",
                "accounting.contacts",
                "accounting.settings",
                "accounting.reports.read",
            ],
            token_auth="basic",
        ),
        "etsy": ProviderConfig(
            name="etsy",
            authorize_url="https://www.etsy.com/oauth/connect",
            token_url="https://api.etsy.com/v3/public/oauth/token",
            client_id=s.etsy_api_key,
            client_secret=s.etsy_shared_secret,
            redirect_uri=s.etsy_redirect_uri,
            scopes=["listings_r", "listings_w", "transactions_r", "shops_r", "shops_w"],
            use_pkce=True,
            token_auth="body",
        ),
        "gmail": ProviderConfig(
            name="gmail",
            authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
            token_url="https://oauth2.googleapis.com/token",
            client_id=s.gmail_client_id,
            client_secret=s.gmail_client_secret,
            redirect_uri=s.gmail_redirect_uri,
            scopes=["https://www.googleapis.com/auth/gmail.readonly"],
            token_auth="body",
            # access_type=offline + prompt=consent forces a refresh token
            extra_authorize_params={"access_type": "offline", "prompt": "consent"},
        ),
        "dropbox": ProviderConfig(
            name="dropbox",
            authorize_url="https://www.dropbox.com/oauth2/authorize",
            token_url="https://api.dropboxapi.com/oauth2/token",
            client_id=s.dropbox_app_key,
            client_secret=s.dropbox_app_secret,
            redirect_uri=s.dropbox_redirect_uri,
            scopes=["files.metadata.read", "files.content.read"],
            token_auth="basic",
            # offline access -> refresh token (Dropbox tokens are short-lived)
            extra_authorize_params={"token_access_type": "offline"},
        ),
    }


def get_provider(name: str) -> ProviderConfig:
    providers = _providers()
    if name not in providers:
        raise KeyError(f"Unknown provider: {name}")
    return providers[name]


def provider_names() -> list[str]:
    return list(_providers().keys())


def make_pkce() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def build_authorize_url(
    p: ProviderConfig, state: str, code_challenge: str | None
) -> str:
    params = {
        "response_type": "code",
        "client_id": p.client_id,
        "redirect_uri": p.redirect_uri,
        "scope": p.scope_separator.join(p.scopes),
        "state": state,
    }
    if p.use_pkce and code_challenge:
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"
    params.update(p.extra_authorize_params)
    return f"{p.authorize_url}?{urlencode(params)}"


def _token_request(p: ProviderConfig, data: dict) -> dict:
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    auth = None
    if p.token_auth == "basic":
        auth = (p.client_id, p.client_secret)
    else:  # "body"
        data = {**data, "client_id": p.client_id}
        if p.client_secret:
            data["client_secret"] = p.client_secret
    resp = httpx.post(p.token_url, data=data, headers=headers, auth=auth, timeout=30)
    resp.raise_for_status()
    return resp.json()


def exchange_code(p: ProviderConfig, code: str, code_verifier: str | None) -> dict:
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": p.redirect_uri,
    }
    if p.use_pkce and code_verifier:
        data["code_verifier"] = code_verifier
    return _token_request(p, data)


def refresh_token(p: ProviderConfig, refresh: str) -> dict:
    return _token_request(p, {"grant_type": "refresh_token", "refresh_token": refresh})


def fetch_xero_tenant(access_token: str) -> str | None:
    """After Xero auth, look up the organisation (tenant) id every API call needs."""
    resp = httpx.get(
        "https://api.xero.com/connections",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    connections = resp.json()
    return connections[0]["tenantId"] if connections else None
