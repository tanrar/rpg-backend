# main.py
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import uuid
from typing import Dict, Optional

from config.settings import Settings
from dependencies import get_settings
from models.session import GameSession
from models.state import GameState
from services.session_service import SessionService

# Initialize FastAPI app
app = FastAPI(
    title="LLM RPG Game API",
    description="Backend API for an LLM-powered RPG game",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
session_service = SessionService()

# Include routers from api modules
from api import sessions, exploration, combat, inventory, character, skill

app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(exploration.router, prefix="/api/sessions/{session_id}/exploration", tags=["exploration"])
app.include_router(combat.router, prefix="/api/sessions/{session_id}/combat", tags=["combat"])
app.include_router(inventory.router, prefix="/api/sessions/{session_id}/inventory", tags=["inventory"])
app.include_router(character.router, prefix="/api/sessions/{session_id}/character", tags=["character"])
app.include_router(skill.router, prefix="/api/sessions/{session_id}/skill", tags=["skill"])

@app.get("/")
async def root(settings: Settings = Depends(get_settings)):
    """Root endpoint for health checks"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running"
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)