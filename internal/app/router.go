package session

import (
	"fmt"
	"llmrpg/character" // Assuming 'llmrpg' is your go module name
	// We don't strictly need to import 'world' here, as we only store the ID,
	// but the concept relies on the world package existing.
	"sync"
	"time"
)

// GameSession holds the state for a single playthrough.
// This is a simplified version for the initial MVP, focusing on Character and Location.
type GameSession struct {
	ID                string             `json:"id"`                  // Unique identifier for this session
	Player            *character.Character `json:"character"`           // The player character for this session
	CurrentLocationID string             `json:"currentLocationId"`   // ID of the player's current location in the world
	CreatedAt         time.Time          `json:"createdAt"`           // When the session started
	LastActive        time.Time          `json:"lastActive"`          // Last time session was accessed/updated
	RecentActions     []string           `json:"recentActions"`       // Limited history for LLM context
	// --- Fields deferred for later implementation based on design ---
	// WorldState      WorldState     `json:"worldState"`        // More complex world state [cite: 161]
	// CurrentScene    Scene          `json:"currentScene"`        // For scene management [cite: 156]
	// SceneHistory    []SceneRecord  `json:"sceneHistory"`      // Longer-term history [cite: 163]
	// Flags           map[string]bool `json:"flags"`             // Narrative flags specific to this session
	// SaveSlot        string         `json:"saveSlot,omitempty"` // Identifier for persistence
}

// Manager defines the interface for managing game sessions.
type Manager interface {
	CreateNewSession(player *character.Character, startLocationID string) (*GameSession, error)
	GetSession(sessionID string) (*GameSession, error)
	GetAllSessionIDs() []string
	UpdateSession(session *GameSession) error // For updating LastActive, etc.
	// DeleteSession(sessionID string) error // Add later if needed
	// SaveSession(sessionID string) error // Add later for persistence
	// LoadSession(sessionID string) (*GameSession, error) // Add later for persistence
}

// InMemorySessionManager stores active game sessions in memory.
type InMemorySessionManager struct {
	sessions map[string]*GameSession
	mu       sync.RWMutex // Protects access to the sessions map
}

// NewInMemorySessionManager creates a new in-memory session manager.
func NewInMemorySessionManager() *InMemorySessionManager {
	return &InMemorySessionManager{
		sessions: make(map[string]*GameSession),
	}
}

// CreateNewSession creates and stores a new game session.
func (sm *InMemorySessionManager) CreateNewSession(player *character.Character, startLocationID string) (*GameSession, error) {
	if player == nil {
		return nil, fmt.Errorf("cannot create session with nil player")
	}
	// Basic validation: ensure player ID is present?
	if player.ID == "" {
		return nil, fmt.Errorf("player must have an ID to create a session")
	}
	// In a real system, you might check if startLocationID is valid using WorldSystem here.

	sm.mu.Lock() // Lock for writing
	defer sm.mu.Unlock()

	// Generate a unique session ID (simple approach for now)
	// A robust solution might use UUIDs or database sequences.
	newID := fmt.Sprintf("session_%s_%d", player.ID, time.Now().UnixNano())

	// Ensure ID uniqueness (highly unlikely collision with nanoseconds, but good practice)
	if _, exists := sm.sessions[newID]; exists {
		// Handle collision (e.g., retry generation, return error)
		return nil, fmt.Errorf("session ID collision detected (highly unlikely)")
	}

	sess := &GameSession{
		ID:                newID,
		Player:            player,
		CurrentLocationID: startLocationID,
		CreatedAt:         time.Now(),
		LastActive:        time.Now(),
		RecentActions:     make([]string, 0, 5), // Initialize with capacity
	}

	sm.sessions[newID] = sess
	fmt.Printf("Created new session: %s for player %s starting at %s\n", newID, player.Name, startLocationID)
	return sess, nil
}

// GetSession retrieves a session by its ID. Updates LastActive time.
func (sm *InMemorySessionManager) GetSession(sessionID string) (*GameSession, error) {
	sm.mu.RLock() // Lock for reading initially
	sess, ok := sm.sessions[sessionID]
	sm.mu.RUnlock() // Unlock after reading

	if !ok {
		return nil, fmt.Errorf("session not found: %s", sessionID)
	}

	// Update LastActive time - requires a write lock temporarily
	sm.mu.Lock()
	sess.LastActive = time.Now()
	sm.mu.Unlock()

	return sess, nil
}

// GetAllSessionIDs returns a slice of all active session IDs.
func (sm *InMemorySessionManager) GetAllSessionIDs() []string {
	sm.mu.RLock()
	defer sm.mu.RUnlock()
	ids := make([]string, 0, len(sm.sessions))
	for id := range sm.sessions {
		ids = append(ids, id)
	}
	// Sort? Optional, but good for deterministic testing/debugging.
	// sort.Strings(ids)
	return ids
}

// UpdateSession allows modifying a session (e.g., adding recent actions, changing location).
// For now, it primarily updates LastActive. More complex updates might need specific methods.
func (sm *InMemorySessionManager) UpdateSession(session *GameSession) error {
	if session == nil {
		return fmt.Errorf("cannot update nil session")
	}

	sm.mu.Lock() // Lock for potential modification
	defer sm.mu.Unlock()

	// Verify the session exists in the manager
	existingSession, ok := sm.sessions[session.ID]
	if !ok {
		return fmt.Errorf("session %s not managed by this manager", session.ID)
	}

	// Update LastActive time
	session.LastActive = time.Now()

	// Replace the stored session pointer with the updated one?
	// Or modify the existing one in place? Modifying in place is common if GetSession returns pointers.
	// Since GetSession updated LastActive already, we might only need this if other fields change.
	// Let's assume modifications happen directly on the pointer returned by GetSession,
	// so this UpdateSession might be more for explicit save triggers later.
	// For now, just ensures it exists.
	_ = existingSession // Use existingSession to avoid unused variable error

	return nil
}

// AddRecentAction adds an action summary to the session's history (limited size).
func (sess *GameSession) AddRecentAction(actionSummary string) {
	// Note: This method modifies the session directly. Ensure thread safety if sessions
	// are accessed concurrently outside the manager's controlled methods.
	// The SessionManager's methods provide safety for accessing the map, but not
	// concurrent modifications *within* a single session object if pointers are shared.
	// For simple sequential request handling, this is likely fine.

	const maxRecentActions = 5 // Keep the last 5 actions
	sess.RecentActions = append(sess.RecentActions, actionSummary)
	if len(sess.RecentActions) > maxRecentActions {
		// Slice off the oldest element
		sess.RecentActions = sess.RecentActions[len(sess.RecentActions)-maxRecentActions:]
	}
}