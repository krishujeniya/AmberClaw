from fastapi import APIRouter, Depends

from amberclaw.api.auth import get_current_user
from amberclaw.api.v1 import (
    a2a,
    agents,
    auth_router,
    budget,
    chat,
    health,
    memory,
    providers_router,
    skills,
    sso_router,
    tickets,
)

api_router = APIRouter()

# Unprotected authentication endpoints (credentials + enterprise SSO)
api_router.include_router(auth_router.router, prefix="/auth", tags=["Auth"])
api_router.include_router(sso_router.router, prefix="/auth/sso", tags=["SSO"])
api_router.include_router(health.router, prefix="/health", tags=["Health"])


# Protected endpoints requiring authentication
protected_router = APIRouter(dependencies=[Depends(get_current_user)])
protected_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
protected_router.include_router(agents.router, prefix="/agents", tags=["Agents"])
protected_router.include_router(a2a.router, prefix="/a2a", tags=["A2A"])
protected_router.include_router(tickets.router, prefix="/tickets", tags=["Tickets"])
protected_router.include_router(
    providers_router.router, prefix="/providers", tags=["Providers"]
)
protected_router.include_router(memory.router, prefix="/memory", tags=["Memory"])
protected_router.include_router(budget.router, prefix="/budget", tags=["Budget"])
protected_router.include_router(skills.router, prefix="/skills", tags=["Skills"])

api_router.include_router(protected_router)


@api_router.get("/")
async def root():
    return {"message": "Welcome to the AmberClaw API v1"}
