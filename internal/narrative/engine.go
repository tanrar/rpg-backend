package narrative

import (
	"context"
	"fmt"
	"llmrpg/internal/llm"     // Adapter interface and data structures
	"llmrpg/internal/session" // Session manager and data structure
	"llmrpg/internal/world"   // World system interface

	// "llmrpg/character" // Character struct (used via session)
	"time"
)

// NarrativeEngine orchestrates the main game loop interaction.
type NarrativeEngine struct {
	WorldSystem    world.WorldSystem
	LLMAdapter     llm.Adapter
	ActionExecutor ActionExecutor
	SessionManager session.Manager // Added dependency to fetch/update sessions
	SystemPrompt   string          // Store the base system prompt
}

// NewNarrativeEngine creates a new engine instance with its dependencies.
func NewNarrativeEngine(ws world.WorldSystem, adapter llm.Adapter, executor ActionExecutor, sm session.Manager, systemPrompt string) (*NarrativeEngine, error) {
	// Validate dependencies
	if ws == nil || adapter == nil || executor == nil || sm == nil {
		return nil, fmt.Errorf("cannot create NarrativeEngine with nil dependencies")
	}
	if systemPrompt == "" {
		// Provide a default or return an error? Let's default for now.
		fmt.Println("Warning: No system prompt provided to NarrativeEngine, using a basic default.")
		systemPrompt = "You are a text-based RPG engine narrating a story. Describe the scene and respond to the player's input. You can suggest actions or trigger game actions using a specific JSON format in the 'actions' field."
	}

	return &NarrativeEngine{
		WorldSystem:    ws,
		LLMAdapter:     adapter,
		ActionExecutor: executor,
		SessionManager: sm,
		SystemPrompt:   systemPrompt,
	}, nil
}

// ProcessPlayerInput takes player input for a given session and processes one turn.
// It returns the LLM's response (narrative, suggestions, potentially raw actions)
// after attempting to execute any valid actions returned by the LLM.
func (ne *NarrativeEngine) ProcessPlayerInput(ctx context.Context, sessionID string, playerInput string) (*llm.LLMResponse, error) {
	// 1. Get current game session
	currentSession, err := ne.SessionManager.GetSession(sessionID)
	if err != nil {
		return nil, fmt.Errorf("failed to retrieve session '%s': %w", sessionID, err)
	}
	// Log player input to session history
	currentSession.AddRecentAction(fmt.Sprintf("Player: %s", playerInput))

	// 2. Build prompt context from session and world state
	promptData, err := ne.buildPromptContext(currentSession)
	if err != nil {
		return nil, fmt.Errorf("failed to build prompt context for session '%s': %w", sessionID, err)
	}
	promptData.PlayerInput = playerInput // Add the current input

	// 3. Call LLM Adapter
	fmt.Printf("NarrativeEngine: Calling LLM adapter for session %s...\n", sessionID)
	llmResponse, err := ne.LLMAdapter.GenerateResponse(ctx, ne.SystemPrompt, *promptData)
	if err != nil {
		// LLM call itself failed (network, API error, etc.)
		// TODO: Consider fallback logic? Generate a default "confused" response?
		return nil, fmt.Errorf("LLM adapter failed for session '%s': %w", sessionID, err)
	}
	// Log LLM narrative to session history? Be mindful of length.
	// currentSession.AddRecentAction(fmt.Sprintf("Narrator: %s", llmResponse.Narrative))

	// 4. Execute Actions returned by LLM
	finalResponse := llmResponse // Start with the direct LLM response
	if len(llmResponse.Actions) > 0 {
		fmt.Printf("NarrativeEngine: Executing %d action(s) for session %s...\n", len(llmResponse.Actions), sessionID)
		executionErrors := ne.ActionExecutor.ExecuteActions(llmResponse.Actions, currentSession)

		if len(executionErrors) > 0 {
			// How to handle action execution errors?
			// - Log them (already done by executor)
			// - Modify the narrative to inform the player?
			// - Return the errors alongside the response?
			// For now, let's prepend an error message to the narrative.
			errorNarrative := fmt.Sprintf("[System Error processing actions: %d error(s) occurred. The story continues...]\n\n", len(executionErrors))
			finalResponse.Narrative = errorNarrative + finalResponse.Narrative

			// Optionally, clear the actions from the response if they failed significantly?
			// Or maybe filter out only the failed actions? For simplicity, keep original actions for now.
			fmt.Printf("NarrativeEngine: Errors occurred during action execution for session %s: %v\n", sessionID, executionErrors)
			// We might return the errors as part of a more complex response object later.
		} else {
			fmt.Printf("NarrativeEngine: All %d action(s) executed successfully for session %s.\n", len(llmResponse.Actions), sessionID)
		}
	}

	// 5. Update session (e.g., LastActive time - already done by GetSession, but explicit save might go here later)
	err = ne.SessionManager.UpdateSession(currentSession)
	if err != nil {
		// Log this error, but probably don't fail the whole turn?
		fmt.Printf("Warning: Failed to update session '%s' after turn: %v\n", sessionID, err)
	}

	// 6. Return the final response (potentially modified narrative)
	return finalResponse, nil
}

// buildPromptContext gathers data from the session and world to create the LLM prompt data.
func (ne *NarrativeEngine) buildPromptContext(currentSession *session.GameSession) (*llm.PromptData, error) {

	// Player Context
	playerCtx := llm.PlayerContextData{
		Name:   currentSession.Player.Name,
		Class:  currentSession.Player.Class,
		Origin: currentSession.Player.Origin,
		Level:  currentSession.Player.Level,
		// Add inventory later
	}

	// Location Context
	currentLoc, err := ne.WorldSystem.GetLocation(currentSession.CurrentLocationID)
	if err != nil {
		// This is critical, fail if we can't get the current location
		return nil, fmt.Errorf("could not get current location details for ID '%s': %w", currentSession.CurrentLocationID, err)
	}

	adjacentLocNodes, err := ne.WorldSystem.GetAdjacentLocations(currentSession.CurrentLocationID)
	if err != nil {
		// Log warning but maybe continue? Or is adjacency essential context? Let's warn and continue.
		fmt.Printf("Warning: Failed to get adjacent locations for '%s': %v\n", currentSession.CurrentLocationID, err)
		adjacentLocNodes = []*world.LocationNode{} // Send empty slice
	}

	adjLocIDs := make([]string, 0, len(adjacentLocNodes))
	adjLocNames := make([]string, 0, len(adjacentLocNodes))
	for _, node := range adjacentLocNodes {
		if node != nil { // Safety check
			adjLocIDs = append(adjLocIDs, node.ID)
			// Important change here: Use ID for name to ensure consistency
			// Format: "location_id (Human Readable Name)"
			adjLocNames = append(adjLocNames, fmt.Sprintf("%s (%s)", node.ID, node.Name))
		}
	}

	locCtx := llm.LocationContextData{
		CurrentLocationName:   fmt.Sprintf("%s (%s)", currentLoc.ID, currentLoc.Name), // Include ID in name
		CurrentLocationDesc:   currentLoc.Description,
		AdjacentLocationIDs:   adjLocIDs,
		AdjacentLocationNames: adjLocNames,
		CurrentThemeID:        currentLoc.ThemeID,
	}

	// Session Context
	sessionCtx := llm.SessionContextData{
		TimeElapsed:   time.Since(currentSession.CreatedAt).Round(time.Second).String(),
		RecentActions: currentSession.RecentActions, // Get limited history
	}

	promptData := &llm.PromptData{
		PlayerContext:   playerCtx,
		LocationContext: locCtx,
		SessionContext:  sessionCtx,
		// PlayerInput is added by the caller (ProcessPlayerInput)
	}

	return promptData, nil
}
