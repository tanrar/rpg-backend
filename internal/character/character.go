package character

// Character holds player-specific data based on the technical design
// We are omitting Inventory and Equipment for the initial MVP focus.
type Character struct {
	ID     string `json:"id"`               // Unique identifier for the character/player
	Name   string `json:"name"`             // Character's name
	Class  string `json:"class,omitempty"`  // e.g., "Psychic", "Courier"
	Origin string `json:"origin,omitempty"` // e.g., "Wasteland-Born"
	Level  int    `json:"level"`            // Starts at 1, progression mechanism TBD
	// Flags map[string]bool `json:"flags,omitempty"` // Optional narrative tags - Consider managing in Session state instead?
	// Appearance string `json:"appearance,omitempty"` // Optional description for prompts
}

// NewCharacter creates a basic character instance with default values.
func NewCharacter(id, name, class, origin string) *Character {
	// Basic validation could be added here (e.g., ensure ID and Name are not empty)
	return &Character{
		ID:     id,
		Name:   name,
		Class:  class,
		Origin: origin,
		Level:  1, // Characters typically start at level 1
	}
}

// Add methods here later if needed, e.g., LevelUp(), AddFlag(), etc.
// For now, it's just a data container.