"""Auth Module — Azure AD SSO + JWT + dev mode bypass

AUTH_MODE=dev  → ข้าม Azure AD, ใช้ mock user (สำหรับ local dev)
AUTH_MODE=prod → validate Azure AD token จริง
"""

import os
from typing import Annotated
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from jose import jwt, JWTError
import httpx

router = APIRouter()

AUTH_MODE = os.getenv("AUTH_MODE", "dev")
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID", "")
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID", "")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
ALGORITHM = "HS256"

# RBAC tier → allowed models
TIER_MODELS = {
    "basic":    ["claude-haiku"],
    "standard": ["claude-haiku", "claude-sonnet"],
    "pro":      ["claude-haiku", "claude-sonnet", "claude-opus"],
    "power":    ["claude-haiku", "claude-sonnet", "claude-opus"],
    "admin":    ["claude-haiku", "claude-sonnet", "claude-opus"],
}


class TokenRequest(BaseModel):
    azure_token: str  # token จาก Azure AD login


class UserInfo(BaseModel):
    user_id: str
    email: str
    department: str
    tier: str
    allowed_models: list[str]


# ── Dev Mode Mock Users ───────────────────────────────────────
DEV_USERS = {
    "dev-basic@precise.co.th":    {"tier": "basic",    "department": "Operations"},
    "dev-standard@precise.co.th": {"tier": "standard", "department": "Engineering"},
    "dev-pro@precise.co.th":      {"tier": "pro",      "department": "Engineering"},
    "dev-power@precise.co.th":    {"tier": "power",    "department": "Management"},
    "dev-admin@precise.co.th":    {"tier": "admin",    "department": "IT"},
}


def _make_internal_token(user: UserInfo) -> str:
    """สร้าง JWT สำหรับใช้ภายใน portal"""
    return jwt.encode(user.model_dump(), SECRET_KEY, algorithm=ALGORITHM)


@router.post("/token")
async def get_token(req: TokenRequest) -> dict:
    """แลก Azure AD token เป็น internal JWT"""
    if AUTH_MODE == "dev":
        # dev: ใช้ azure_token เป็น email โดยตรง
        email = req.azure_token
        mock = DEV_USERS.get(email)
        if not mock:
            raise HTTPException(status_code=401, detail="Unknown dev user email")
        user = UserInfo(
            user_id=f"dev-{email}",
            email=email,
            department=mock["department"],
            tier=mock["tier"],
            allowed_models=TIER_MODELS[mock["tier"]],
        )
        return {"access_token": _make_internal_token(user), "token_type": "bearer"}

    # prod: validate Azure AD token
    claims = await _validate_azure_token(req.azure_token)
    tier = claims.get("extension_pcc_tier", "basic")  # custom claim จาก Azure AD
    user = UserInfo(
        user_id=claims["oid"],
        email=claims.get("upn", claims.get("email", "")),
        department=claims.get("department", "Unknown"),
        tier=tier,
        allowed_models=TIER_MODELS.get(tier, TIER_MODELS["basic"]),
    )
    return {"access_token": _make_internal_token(user), "token_type": "bearer"}


async def _validate_azure_token(token: str) -> dict:
    """Validate Azure AD JWT token"""
    jwks_url = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/discovery/v2.0/keys"
    async with httpx.AsyncClient() as client:
        resp = await client.get(jwks_url)
        resp.raise_for_status()
    try:
        claims = jwt.decode(
            token,
            resp.json(),
            algorithms=["RS256"],
            audience=AZURE_CLIENT_ID,
        )
        return claims
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid Azure token: {e}")


def get_current_user(authorization: Annotated[str | None, Header()] = None) -> UserInfo:
    """Dependency — parse internal JWT จาก Authorization header"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    token = authorization.removeprefix("Bearer ")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return UserInfo(**payload)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.get("/me")
def me(user: Annotated[UserInfo, Depends(get_current_user)]) -> UserInfo:
    return user
