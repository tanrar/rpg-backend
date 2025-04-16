package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net/http"
	"os"
	"strings" // Needed for handleUpdateLocation check in narrative/executor.go (imported there)
	"time"

	// Import godotenv library
	"github.com/joho/godotenv"

	// Import internal packages
	"llmrpg/internal/character"
	"llmrpg/internal/llm"
	"llmrpg/internal/narrative"
	"llmrpg/internal/session"
	"llmrpg/internal/world"
)

// --- Global System Variables ---
// These are initialized in main()
var worldSystem world.WorldSystem
var sessionManager session.Manager
var llmAdapter llm.Adapter
var actionExecutor narrative.ActionExecutor
var narrativeEngine *narrative.NarrativeEngine

// --- CORS Middleware ---

// corsMiddleware adds necessary CORS headers to allow requests from the frontend development server.
// It wraps an existing http.HandlerFunc.
func corsMiddleware(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Set allowed origin (adjust if your frontend runs on a different port)
		// Using "*" is generally okay for local development but be more specific for production.
		// Ensure your frontend origin (e.g., http://localhost:3000) is allowed.
		allowedOrigin := os.Getenv("ALLOWED_ORIGIN")
		if allowedOrigin == "" {
			allowedOrigin = "http://localhost:3000" // Default frontend dev server
		}
		w.Header().Set("Access-Control-Allow-Origin", allowedOrigin)

		// Set allowed methods
		w.Header().Set("Access-Control-Allow-Methods", "POST, GET, OPTIONS, PUT, DELETE")

		// Set allowed headers that the frontend might send
		w.Header().Set("Access-Control-Allow-Headers", "Accept, Content-Type, Content-Length, Accept-Encoding, X-CSRF-Token, Authorization")

		// Set credentials header if needed (e.g., for cookies, authorization headers)
		// w.Header().Set("Access-Control-Allow-Credentials", "true")

		// Handle preflight OPTIONS requests
		if r.Method == "OPTIONS" {
			w.WriteHeader(http.StatusOK) // Respond OK to OPTIONS preflight
			return                       // Don't call the next handler for OPTIONS
		}

		// Call the actual handler for other methods (GET, POST, etc.)
		next(w, r)
	}
}

// --- Main Function ---

func main() {
	// --- Load .env file ---
	// Call godotenv.Load() BEFORE trying to read environment variables.
	// It loads variables from the ".env" file in the current working directory.
	err := godotenv.Load()
	if err != nil {
		// Load() doesn't error if ".env" is missing by default.
		// Log this as a warning unless the .env is absolutely required.
		log.Println("Warning: .env file not found or error loading it:", err)
	} else {
		fmt.Println("Successfully loaded .env file.")
	}

	// --- System Initialization ---
	fmt.Println("Initializing systems...")

	// Initialize World System
	worldSystem = world.NewInMemoryWorldSystem()
	locPath := os.Getenv("LOCATION_DATA_PATH")
	themePath := os.Getenv("THEME_DATA_PATH")
	if locPath == "" || themePath == "" {
		log.Fatal("FATAL: LOCATION_DATA_PATH and THEME_DATA_PATH environment variables must be set (check .env or system env)")
	}
	if err := worldSystem.LoadWorldData(locPath, themePath); err != nil {
		log.Fatalf("FATAL: Failed to load world data from '%s' and '%s': %v", locPath, themePath, err)
	}
	fmt.Println("World system loaded.")

	// Initialize Session Manager
	sessionManager = session.NewInMemorySessionManager()
	fmt.Println("Session manager initialized.")

	// Initialize LLM Adapter
	modelName := os.Getenv("GEMINI_MODEL_NAME")
	if modelName == "" {
		modelName = "gemini-1.5-flash-latest" // Default model
	}
	apiKey := os.Getenv("GEMINI_API_KEY")
	if apiKey == "" {
		// Decide if this is fatal or just a warning
		log.Println("Warning: GEMINI_API_KEY environment variable not set (check .env or system env). LLM calls will fail.")
		// log.Fatal("FATAL: GEMINI_API_KEY must be set")
	}
	llmAdapter = llm.NewGeminiAdapter(modelName) // Assumes NewGeminiAdapter doesn't immediately need the key
	fmt.Printf("LLM adapter initialized (Model: %s).\n", modelName)

	// Initialize Action Executor
	// Inject dependencies needed by the executor (currently just WorldSystem)
	actionExecutor = narrative.NewSimpleActionExecutor(worldSystem /*, inventorySystem, etc */)
	fmt.Println("Action executor initialized.")

	// Initialize Narrative Engine
	// Load system prompt from file or use default
	defaultPromptPath := "data/prompts/system_prompt.txt" // Default system prompt path
	systemPromptPath := os.Getenv("SYSTEM_PROMPT_PATH")
	if systemPromptPath == "" {
		systemPromptPath = defaultPromptPath
		fmt.Printf("Using default prompt path: %s\n", defaultPromptPath)
	}

	var systemPrompt string
	promptBytes, err := os.ReadFile(systemPromptPath)
	if err != nil {
		// Truly minimal fallback prompt as last resort
		systemPrompt = `You are the narrator for a text adventure game. Describe the world vividly and respond to player actions.`
		log.Printf("Warning: Failed to read system prompt from %s: %v. Using minimal fallback.", systemPromptPath, err)
	} else {
		systemPrompt = string(promptBytes)
		fmt.Printf("Loaded system prompt from %s (%d bytes)\n", systemPromptPath, len(promptBytes))
	}
	narrativeEngine, err = narrative.NewNarrativeEngine(worldSystem, llmAdapter, actionExecutor, sessionManager, systemPrompt)
	if err != nil {
		log.Fatalf("FATAL: Failed to create narrative engine: %v", err)
	}
	fmt.Println("Narrative engine initialized.")

	// Attempt to Create a Default Session (for testing/convenience)
	createDefaultSession()

	// --- HTTP Server Setup ---
	// Register handlers and wrap them with CORS middleware
	http.HandleFunc("/action", corsMiddleware(handleAction))
	http.HandleFunc("/state", corsMiddleware(handleGetState))
	http.HandleFunc("/create_session", corsMiddleware(handleCreateSession))
	http.HandleFunc("/health", corsMiddleware(handleHealthCheck)) // Basic health check

	// Determine port
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080" // Default port
	}

	fmt.Printf("Starting llmrpg server on port %s with CORS enabled for origin: %s...\n", port, os.Getenv("ALLOWED_ORIGIN"))
	// Start listening
	log.Fatal(http.ListenAndServe(":"+port, nil))
}

// --- Helper Functions ---

// createDefaultSession creates a default session if none exist (useful for development)
func createDefaultSession() {
	// Check if any sessions already exist
	if len(sessionManager.GetAllSessionIDs()) > 0 {
		fmt.Println("Default session creation skipped: Sessions already exist.")
		return
	}

	// Define default character and starting location
	player := character.NewCharacter("player_default", "Ash", "Wasteland-Born", "Courier")
	startLocationID := "oakhaven_gate" // Default start location ID from sample data

	// Verify start location exists
	if len(worldSystem.GetAllLocationIDs()) > 0 {
		if _, err := worldSystem.GetLocation(startLocationID); err != nil {
			fmt.Printf("Warning: Default start location '%s' not found. Using first available location.\n", startLocationID)
			startLocationID = worldSystem.GetAllLocationIDs()[0] // Fallback to first loaded location
		}
	} else {
		log.Println("Warning: Cannot create default session: No locations loaded.")
		return // Cannot create session without locations
	}

	// Create the session
	_, err := sessionManager.CreateNewSession(player, startLocationID)
	if err != nil {
		// Log failure but don't necessarily stop the server
		log.Printf("Warning: Failed to create default session: %v", err)
	} else {
		fmt.Println("Default session created successfully.")
	}
}

// --- HTTP Handlers ---

// handleAction processes player input via the NarrativeEngine.
func handleAction(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Get Session ID from query parameter
	sessionID := r.URL.Query().Get("sessionId")
	if sessionID == "" {
		// Fallback for testing/convenience: use the first available session ID
		ids := sessionManager.GetAllSessionIDs()
		if len(ids) > 0 {
			sessionID = ids[0]
			fmt.Println("Warning: No sessionId provided in /action request, using first available:", sessionID)
		} else {
			http.Error(w, "No active session found and no sessionId provided", http.StatusBadRequest)
			return
		}
	}

	// Decode request body
	var requestBody struct {
		Input string `json:"input"`
	}
	if err := json.NewDecoder(r.Body).Decode(&requestBody); err != nil {
		http.Error(w, fmt.Sprintf("Invalid request body: %v", err), http.StatusBadRequest)
		return
	}
	if requestBody.Input == "" {
		http.Error(w, "Missing 'input' in request body", http.StatusBadRequest)
		return
	}

	// Process input using the engine
	ctx := r.Context() // Use request context for potential cancellation
	llmResponse, err := narrativeEngine.ProcessPlayerInput(ctx, sessionID, requestBody.Input)

	// Handle errors from the engine
	if err != nil {
		log.Printf("ERROR [handleAction Session: %s]: %v\n", sessionID, err)
		// Check if the error is due to client disconnecting
		if errors.Is(err, context.Canceled) {
			http.Error(w, "Request cancelled by client.", 499) // 499 Client Closed Request
			return
		}
		// Return a generic server error to the client
		http.Error(w, "Failed to process input due to an internal server error.", http.StatusInternalServerError)
		return
	}

	// Send successful response
	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(llmResponse); err != nil {
		// Log error if encoding fails (response might be partially sent)
		log.Printf("ERROR [handleAction Session: %s]: Failed to encode response: %v\n", sessionID, err)
	}
}

// handleGetState retrieves the current state for a given session.
func handleGetState(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Get Session ID from query parameter
	sessionID := r.URL.Query().Get("sessionId")
	if sessionID == "" {
		// Fallback for testing/convenience
		ids := sessionManager.GetAllSessionIDs()
		if len(ids) > 0 {
			sessionID = ids[0]
			fmt.Println("Warning: No sessionId provided in /state request, using first available:", sessionID)
		} else {
			http.Error(w, "No active session found", http.StatusNotFound)
			return
		}
	}

	// Get session data
	currentSession, err := sessionManager.GetSession(sessionID)
	if err != nil {
		// Log error and return appropriate HTTP status
		log.Printf("INFO [handleGetState]: Session not found: %v\n", err)
		http.Error(w, fmt.Sprintf("Session not found: %s", sessionID), http.StatusNotFound)
		return
	}

	// --- Crucial Backend Change for Theme/Image Handling ---
	// Fetch and attach the current location details to the session object before sending.
	locationDetails, locErr := worldSystem.GetLocation(currentSession.CurrentLocationID)
	if locErr != nil {
		log.Printf("Warning [handleGetState Session: %s]: Could not fetch location details for %s: %v\n", sessionID, currentSession.CurrentLocationID, locErr)
		currentSession.CurrentLocation = nil // Ensure it's explicitly null if fetch failed
	} else {
		currentSession.CurrentLocation = locationDetails // Attach the details
	}
	// --- End Backend Change ---

	// Send successful response
	w.Header().Set("Content-Type", "application/json")
	if err := json.NewEncoder(w).Encode(currentSession); err != nil {
		log.Printf("ERROR [handleGetState Session: %s]: Failed to encode state response: %v\n", sessionID, err)
		// Don't write header again if encoding fails after starting response
	}
}

// handleCreateSession creates a new game session.
func handleCreateSession(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Decode request body for player details and start location
	var req struct {
		PlayerName      string `json:"playerName"`
		ClassName       string `json:"className"`  // Optional
		OriginName      string `json:"originName"` // Optional
		StartLocationID string `json:"startLocationId"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, fmt.Sprintf("Invalid request body: %v", err), http.StatusBadRequest)
		return
	}

	// Validate required fields
	if req.PlayerName == "" || req.StartLocationID == "" {
		http.Error(w, "Missing required fields: playerName and startLocationId", http.StatusBadRequest)
		return
	}

	// Validate start location exists
	if _, err := worldSystem.GetLocation(req.StartLocationID); err != nil {
		http.Error(w, fmt.Sprintf("Invalid start location ID '%s': %v", req.StartLocationID, err), http.StatusBadRequest)
		return
	}

	// Create character and new session
	// Generate a simple unique player ID
	playerID := fmt.Sprintf("player_%s_%d", strings.ToLower(req.PlayerName), time.Now().UnixNano())
	player := character.NewCharacter(playerID, req.PlayerName, req.ClassName, req.OriginName)

	newSession, err := sessionManager.CreateNewSession(player, req.StartLocationID)
	if err != nil {
		log.Printf("ERROR [handleCreateSession]: Failed to create session: %v\n", err)
		http.Error(w, "Failed to create session due to an internal error.", http.StatusInternalServerError)
		return
	}

	// Attach location details to the response for the new session
	locationDetails, locErr := worldSystem.GetLocation(newSession.CurrentLocationID)
	if locErr != nil {
		log.Printf("Warning [handleCreateSession Session: %s]: Could not fetch location details for new session response: %v\n", newSession.ID, locErr)
		newSession.CurrentLocation = nil
	} else {
		newSession.CurrentLocation = locationDetails
	}

	// Send successful response (201 Created)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated) // Use 201 for resource creation
	if err := json.NewEncoder(w).Encode(newSession); err != nil {
		log.Printf("ERROR [handleCreateSession Session: %s]: Failed to encode new session response: %v\n", newSession.ID, err)
	}
}

// handleHealthCheck provides a simple endpoint to check server status.
func handleHealthCheck(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	// Simple JSON response is often preferred over plain text
	json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}

// --- Ensure necessary standard library imports ---
// Included at the top
