package narrative

import (
	"errors"
	"fmt"
	"llmrpg/internal/llm"     // For llm.LLMAction definition
	"llmrpg/internal/session" // For session.GameSession definition
	"llmrpg/internal/world"   // For world.WorldSystem interface
	"strings"

	// Import other system packages (like inventory, character) here when needed
)

// ActionType defines the valid types of actions the LLM can request,
// based on the exposed capabilities. [cite: 88, 126]
type ActionType string

const (
	// MVP Actions
	UpdateLocation ActionType = "updateLocation"
	AddItem        ActionType = "addItem"    // To be implemented with InventorySystem
	RemoveItem     ActionType = "removeItem" // To be implemented with InventorySystem
	ApplyEffect    ActionType = "applyEffect" // To be implemented with CharacterSystem/EffectSystem

	// Add other action types later (e.g., initiateCombat, startDialogue)
)

// ExecutionResult could potentially hold more info about the outcome of an action
// type ExecutionResult struct {
// 	ActionType ActionType
// 	Success    bool
// 	Message    string
// 	Error      error
// }

// ActionExecutor defines the interface for handling LLM actions.
type ActionExecutor interface {
	// ExecuteActions processes a list of actions, modifying the session state.
	// It returns a slice of errors encountered during execution (one per failed action, potentially).
	ExecuteActions(actions []llm.LLMAction, currentSession *session.GameSession) []error
}

// SimpleActionExecutor implements the execution logic using injected system dependencies.
type SimpleActionExecutor struct {
	WorldSystem world.WorldSystem
	// Add InventorySystem inventory.System later
	// Add CharacterSystem character.System later
}

// NewSimpleActionExecutor creates a new action executor.
// We inject dependencies (like WorldSystem) here.
func NewSimpleActionExecutor(ws world.WorldSystem /* Add other systems as params */) *SimpleActionExecutor {
	if ws == nil {
		// Or handle this more gracefully depending on requirements
		panic("WorldSystem cannot be nil for SimpleActionExecutor")
	}
	return &SimpleActionExecutor{
		WorldSystem: ws,
	}
}

// ExecuteActions processes actions returned by the LLM against the current game session.
func (e *SimpleActionExecutor) ExecuteActions(actions []llm.LLMAction, currentSession *session.GameSession) []error {
	var executionErrors []error

	if currentSession == nil {
		// This shouldn't happen if called correctly from the game loop
		return []error{errors.New("cannot execute actions on a nil session")}
	}

	// It might be important to execute actions sequentially as one might depend on the state change of another.
	for _, action := range actions {
		var err error
		actionType := ActionType(action.Type) // Convert string to our defined type

		fmt.Printf("Executor: Processing action type '%s'\n", actionType)

		switch actionType {
		case UpdateLocation:
			err = e.handleUpdateLocation(action, currentSession)
		case AddItem:
			// Placeholder - Requires InventorySystem
			err = fmt.Errorf("action type '%s' requires InventorySystem (not implemented yet)", actionType)
			// err = e.handleAddItem(action, currentSession)
		case RemoveItem:
			// Placeholder - Requires InventorySystem
			err = fmt.Errorf("action type '%s' requires InventorySystem (not implemented yet)", actionType)
			// err = e.handleRemoveItem(action, currentSession)
		case ApplyEffect:
			// Placeholder - Requires Character/Effect System
			err = fmt.Errorf("action type '%s' requires Character/EffectSystem (not implemented yet)", actionType)
			// err = e.handleApplyEffect(action, currentSession)
		default:
			err = fmt.Errorf("unknown or unsupported action type received from LLM: '%s'", action.Type)
		}

		// Collect errors. Decide if execution should stop on first error?
		// For now, continue processing other actions but log/collect all errors.
		if err != nil {
			// Wrap error for more context
			wrappedErr := fmt.Errorf("failed to execute action (type: %s, data: %v): %w", action.Type, action.Data, err)
			executionErrors = append(executionErrors, wrappedErr)
			fmt.Printf("Executor Error: %v\n", wrappedErr) // Log error
		} else {
			// Log successful action execution to session history?
            // Note: This assumes modification happens directly on the session pointer.
			currentSession.AddRecentAction(fmt.Sprintf("System executed: %s", actionType))
		}
	}

	// Persist session changes after all actions? Or rely on caller?
	// For an in-memory session manager, changes are already applied to the session object.
	// Persistence would be handled separately by the main loop/session manager.

	return executionErrors // Return nil if no errors occurred
}

// handleUpdateLocation processes the 'updateLocation' action.
// It validates the target location and updates the session state.
func (e *SimpleActionExecutor) handleUpdateLocation(action llm.LLMAction, currentSession *session.GameSession) error {
	// 1. Validate Data Structure
	locationIDData, ok := action.Data["locationId"]
	if !ok {
		return errors.New("action data missing required field 'locationId'")
	}

	targetLocationID, ok := locationIDData.(string)
	if !ok {
		return errors.New("action data field 'locationId' must be a string")
	}

	if targetLocationID == "" {
		return errors.New("action data field 'locationId' cannot be empty")
	}

	currentLocationID := currentSession.CurrentLocationID
	if currentLocationID == targetLocationID {
		// Optional: Treat moving to the same location as a no-op success or a specific info message?
		fmt.Printf("Executor Info: Player already at location '%s'. No move needed.\n", targetLocationID)
		return nil // Or return a specific kind of non-error status if needed
	}

	// 2. Validate Game Logic (using WorldSystem)
	fmt.Printf("Executor: Validating move from '%s' to '%s'\n", currentLocationID, targetLocationID)
	isAdj, err := e.WorldSystem.IsAdjacent(currentLocationID, targetLocationID)
	if err != nil {
		// Check if the error was due to non-existence vs other issues
		if strings.Contains(err.Error(), "not found") {
             return fmt.Errorf("validation failed - location does not exist: %w", err)
        }
		return fmt.Errorf("error checking adjacency via WorldSystem: %w", err)
	}

	if !isAdj {
		// LLM suggested an invalid move according to world rules
		return fmt.Errorf("validation failed - target location '%s' is not adjacent to current location '%s'", targetLocationID, currentLocationID)
	}

	// 3. Apply State Change
	fmt.Printf("Executor: Move validated. Updating session location for player '%s' to '%s'\n", currentSession.Player.ID, targetLocationID)
	currentSession.CurrentLocationID = targetLocationID

	// Potentially trigger other effects related to location change (e.g., clear temporary flags)

	return nil // Success
}

// --- Placeholder handlers for future actions ---

// func (e *SimpleActionExecutor) handleAddItem(action llm.LLMAction, currentSession *session.GameSession) error {
// 	// 1. Validate Data (itemId, count)
// 	// 2. Call InventorySystem.AddItem(currentSession.Player.ID, itemId, count)
// 	// 3. Handle errors from InventorySystem
// 	return errors.New("handleAddItem not implemented")
// }

// func (e *SimpleActionExecutor) handleRemoveItem(action llm.LLMAction, currentSession *session.GameSession) error {
// 	// 1. Validate Data (itemId, count)
// 	// 2. Call InventorySystem.RemoveItem(currentSession.Player.ID, itemId, count)
// 	// 3. Handle errors (e.g., item not found, insufficient count)
// 	return errors.New("handleRemoveItem not implemented")
// }

// func (e *SimpleActionExecutor) handleApplyEffect(action llm.LLMAction, currentSession *session.GameSession) error {
// 	// 1. Validate Data (effectId, duration, description, target?)
// 	// 2. Call CharacterSystem.ApplyEffect(currentSession.Player.ID, effectData)
// 	// 3. Handle errors
// 	return errors.New("handleApplyEffect not implemented")
// }