from fastapi import APIRouter, Request

from app.api.deps import SettingsDep

router = APIRouter(tags=["meta"])


@router.get("/health")
async def health(request: Request, settings: SettingsDep) -> dict:
    mode = "live" if getattr(request.app.state, "keitaro", None) else "not_configured"
    return {
        "status": "ok",
        "keitaro": mode,
        "keitaro_url": settings.keitaro_url or None,
        "campaign_name_prefix": settings.campaign_name_prefix,
        "google_redirect_url": settings.google_redirect_url,
    }
