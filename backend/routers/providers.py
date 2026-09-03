"""DataForge AI - AI provider status & test endpoints. Never exposes API keys."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.ai.manager import ai_manager
from backend.config import settings

router = APIRouter(prefix="/api/ai", tags=["providers"])


@router.get("/providers")
def list_providers():
    status = ai_manager.status()
    for s in status:
        s["role"] = (
            "primary" if s["provider"] == settings.PRIMARY_AI_PROVIDER else
            "fallback" if s["provider"] == settings.FALLBACK_AI_PROVIDER else
            "secondary_fallback" if s["provider"] == settings.SECONDARY_FALLBACK_AI_PROVIDER else
            "unused"
        )
    return {
        "providers": status,
        "fallback_order": [settings.PRIMARY_AI_PROVIDER, settings.FALLBACK_AI_PROVIDER,
                            settings.SECONDARY_FALLBACK_AI_PROVIDER],
    }


@router.post("/test/{provider}")
async def test_provider(provider: str, db: Session = Depends(get_db)):
    if provider not in ai_manager.providers:
        raise HTTPException(status_code=404, detail=f"Unknown provider '{provider}'.")
    return await ai_manager.test_provider(provider, db)


@router.post("/test-all")
async def test_all_providers(db: Session = Depends(get_db)):
    results = []
    for name in ai_manager.providers:
        results.append(await ai_manager.test_provider(name, db))
    return {"results": results}
