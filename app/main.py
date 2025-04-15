# app/main.py (updated version)
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.api import sessions
from app.api.exploration import router as exploration_router
from app.config.settings import Settings
from app.services.state_factory import StateServiceFactory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load settings
settings = Settings()


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""

    application = FastAPI(
        title="LLM-Powered RPG API",
        description="API for an LLM-powered role-playing game",
        version="0.1.0",
    )

    # Configure CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    application.include_router(
        sessions.router, prefix="/api/sessions", tags=["Sessions"]
    )
    application.include_router(exploration_router, prefix="/api/sessions/{session_id}/exploration", tags=["Exploration"])


    # Add startup event
    @application.on_event("startup")
    async def startup_event():
        logger.info("Starting up the application")
        # Initialize state handlers
        await StateServiceFactory.initialize()

    # Add shutdown event
    @application.on_event("shutdown")
    async def shutdown_event():
        logger.info("Shutting down the application")

    return application


app = create_application()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
