from fastapi import APIRouter

from amberclaw.api.v1 import agents, a2a, tickets

api_router = APIRouter()

# Example of how we will wire sub-routers:
api_router.include_router(agents.router, prefix="/agents", tags=["Agents"])
api_router.include_router(a2a.router, prefix="/a2a", tags=["A2A"])
api_router.include_router(tickets.router, prefix="/tickets", tags=["Tickets"])
# api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
# api_router.include_router(memory.router, prefix="/memory", tags=["Memory"])
# api_router.include_router(skills.router, prefix="/skills", tags=["Skills"])

@api_router.get("/")
async def root():
    return {"message": "Welcome to the AmberClaw API v1"}
