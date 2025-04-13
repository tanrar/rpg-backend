# services/session_service.py
import json
import os
from typing import Dict, List, Optional
import time
import threading
from datetime import datetime, timedelta

from config.settings import Settings
from models.session import GameSession

class SessionService:
    """Service for managing game sessions"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern to ensure there's only one session manager"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(SessionService, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        """Initialize the session service"""
        if self._initialized:
            return
            
        self.settings = Settings()
        self.sessions: Dict[str, GameSession] = {}
        self.last_cleanup = time.time()
        self._initialized = True
        
        # Ensure storage directory exists
        if self.settings.storage_type == "json":
            os.makedirs(self.settings.storage_path, exist_ok=True)
            
        # Load any existing sessions
        self._load_sessions()
    
    def _load_sessions(self) -> None:
        """Load saved sessions from storage"""
        if self.settings.storage_type != "json":
            return  # Only implement JSON storage for now
            
        try:
            session_dir = os.path.join(self.settings.storage_path, "sessions")
            if not os.path.exists(session_dir):
                os.makedirs(session_dir, exist_ok=True)
                return
                
            for filename in os.listdir(session_dir):
                if filename.endswith('.json'):
                    try:
                        with open(os.path.join(session_dir, filename), 'r') as f:
                            session_data = json.load(f)
                            session = GameSession(**session_data)
                            self.sessions[session.session_id] = session
                    except Exception as e:
                        print(f"Error loading session {filename}: {e}")
        except Exception as e:
            print(f"Error loading sessions: {e}")
    
    def _save_session(self, session: GameSession) -> bool:
        """Save a session to storage"""
        if self.settings.storage_type != "json":
            return False  # Only implement JSON storage for now
            
        try:
            session_dir = os.path.join(self.settings.storage_path, "sessions")
            os.makedirs(session_dir, exist_ok=True)
            
            filename = os.path.join(session_dir, f"{session.session_id}.json")
            with open(filename, 'w') as f:
                f.write(session.json(indent=2))
            return True
        except Exception as e:
            print(f"Error saving session {session.session_id}: {e}")
            return False
    
    def _cleanup_old_sessions(self) -> None:
        """Remove expired sessions"""
        # Only run cleanup periodically
        current_time = time.time()
        if current_time - self.last_cleanup < 3600:  # Run once per hour
            return
            
        self.last_cleanup = current_time
        cutoff_time = datetime.now() - timedelta(seconds=self.settings.max_session_age)
        
        expired_sessions = []
        for session_id, session in self.sessions.items():
            if session.updated_at < cutoff_time:
                expired_sessions.append(session_id)
                
        for session_id in expired_sessions:
            self.end_session(session_id)
    
    def create_session(self, player_name: str, character_class: str, origin: str) -> GameSession:
        """Create a new game session"""
        session = GameSession.create(player_name, character_class, origin)
        self.sessions[session.session_id] = session
        self._save_session(session)
        return session
    
    def get_session(self, session_id: str) -> Optional[GameSession]:
        """Get a session by ID"""
        self._cleanup_old_sessions()
        return self.sessions.get(session_id)
    
    def update_session(self, session: GameSession) -> bool:
        """Update a session in storage"""
        session.update_timestamp()
        self.sessions[session.session_id] = session
        return self._save_session(session)
    
    def end_session(self, session_id: str) -> bool:
        """End a session and remove it from storage"""
        if session_id not in self.sessions:
            return False
            
        # Final save before removal
        self._save_session(self.sessions[session_id])
        
        # Remove from memory
        del self.sessions[session_id]
        
        # Remove from disk if using JSON storage
        if self.settings.storage_type == "json":
            try:
                filename = os.path.join(
                    self.settings.storage_path, 
                    "sessions", 
                    f"{session_id}.json"
                )
                if os.path.exists(filename):
                    os.remove(filename)
            except Exception as e:
                print(f"Error removing session file: {e}")
                return False
                
        return True
    
    def list_sessions(self) -> List[Dict]:
        """List all active sessions"""
        self._cleanup_old_sessions()
        return [
            {
                "session_id": s.session_id,
                "player_name": s.player.name,
                "character_class": s.player.character_class,
                "level": s.player.level,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
            }
            for s in self.sessions.values()
        ]