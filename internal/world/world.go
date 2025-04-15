package world

import (
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"sync"
)

// LocationNode remains the same - it stores the ThemeID string
type LocationNode struct {
	ID             string                 `json:"id"`
	Name           string                 `json:"name"`
	Description    string                 `json:"description"`
	AdjacentIDs    []string               `json:"adjacentIds,omitempty"`
	Tags           []string               `json:"tags,omitempty"`
	ImageID        string                 `json:"imageId,omitempty"`
	ThemeID        string                 `json:"themeId,omitempty"` // This ID is sent to the frontend
	Attributes     map[string]interface{} `json:"attributes,omitempty"`
}

// ThemeDefinition can be simplified. Its primary purpose in the backend
// is now potentially just validating that a theme ID exists.
// We might not even need to store much beyond the ID itself.
// Keeping Name for potential display/debugging. [Original definition: cite: 112-113]
type ThemeDefinition struct {
	ID   string `json:"id"`   // Ensure JSON 'id' matches filename/key
	Name string `json:"name"` // Optional: Useful for debugging/listing
	// CSSClass string `json:"cssClass"` // REMOVED from backend responsibility
	// Palette map[string]string `json:"palette,omitempty"` // REMOVED
}

// WorldSystem interface remains largely the same, but GetTheme might be less critical
// or just return the ThemeDefinition struct (which is now simpler).
type WorldSystem interface {
	LoadWorldData(locationDir, themeDir string) error
	GetLocation(locationID string) (*LocationNode, error)
	GetTheme(themeID string) (*ThemeDefinition, error)
	IsAdjacent(currentLocationID, targetLocationID string) (bool, error)
	GetAllLocationIDs() []string
	GetAllThemeIDs() []string
	ValidateThemeExists(themeID string) bool
    GetAdjacentLocations(locationID string) ([]*LocationNode, error) 
}
// InMemoryWorldSystem holds loaded world data.
type InMemoryWorldSystem struct {
	locations map[string]*LocationNode
	themes    map[string]*ThemeDefinition // Stores the simplified ThemeDefinition
	mu        sync.RWMutex
}

// NewInMemoryWorldSystem creates a new, empty world system.
func NewInMemoryWorldSystem() *InMemoryWorldSystem {
	return &InMemoryWorldSystem{
		locations: make(map[string]*LocationNode),
		themes:    make(map[string]*ThemeDefinition),
	}
}

// LoadWorldData reads location and theme definitions.
func (ws *InMemoryWorldSystem) LoadWorldData(locationDir, themeDir string) error {
	ws.mu.Lock()
	defer ws.mu.Unlock()

	ws.locations = make(map[string]*LocationNode)
	ws.themes = make(map[string]*ThemeDefinition)

	var loadErrors []error

	// --- Load Themes First (so locations can reference them) ---
	fmt.Printf("Loading themes from: %s\n", themeDir)
	err := filepath.WalkDir(themeDir, func(path string, d fs.DirEntry, err error) error {
		// ... (error handling as before) ...
		if !d.IsDir() && strings.HasSuffix(strings.ToLower(d.Name()), ".json") {
            fmt.Printf("  Processing theme file: %s\n", d.Name())
			content, err := os.ReadFile(path)
			if err != nil {
				loadErrors = append(loadErrors, fmt.Errorf("failed to read theme file %s: %w", d.Name(), err))
				return nil
			}
			// ... (error handling) ...

			var theme ThemeDefinition // Use the simplified struct
			if err := json.Unmarshal(content, &theme); err != nil {
                loadErrors = append(loadErrors, fmt.Errorf("failed to parse theme JSON %s: %w", d.Name(), err))
				return nil
			}

			if theme.ID == "" {
				theme.ID = strings.TrimSuffix(d.Name(), filepath.Ext(d.Name()))
                fmt.Printf("    Warning: Theme file %s missing 'id' field, using filename '%s' as ID.\n", d.Name(), theme.ID)
			}

			if _, exists := ws.themes[theme.ID]; exists {
				loadErrors = append(loadErrors, fmt.Errorf("duplicate theme ID '%s' found (from file %s)", theme.ID, d.Name()))
				return nil
			}
			ws.themes[theme.ID] = &theme // Store the simplified theme definition
            fmt.Printf("    Loaded theme definition: %s (%s)\n", theme.Name, theme.ID)
		}
		return nil
	})
    if err != nil {
		loadErrors = append(loadErrors, fmt.Errorf("error walking theme directory %s: %w", themeDir, err))
	}


	// --- Load Locations ---
	fmt.Printf("Loading locations from: %s\n", locationDir)
	err = filepath.WalkDir(locationDir, func(path string, d fs.DirEntry, err error) error {
		// ... (error handling as before) ...
		if !d.IsDir() && strings.HasSuffix(strings.ToLower(d.Name()), ".json") {
            fmt.Printf("  Processing location file: %s\n", d.Name())
			content, err := os.ReadFile(path)
			if err != nil {
				loadErrors = append(loadErrors, fmt.Errorf("failed to read location file %s: %w", d.Name(), err))
				return nil
			}
			// ... (error handling) ...

			var loc LocationNode
			if err := json.Unmarshal(content, &loc); err != nil {
                loadErrors = append(loadErrors, fmt.Errorf("failed to parse location JSON %s: %w", d.Name(), err))
				return nil
			}

            if loc.ID == "" {
                loc.ID = strings.TrimSuffix(d.Name(), filepath.Ext(d.Name()))
                fmt.Printf("    Warning: Location file %s missing 'id' field, using filename '%s' as ID.\n", d.Name(), loc.ID)
            }

			if _, exists := ws.locations[loc.ID]; exists {
				loadErrors = append(loadErrors, fmt.Errorf("duplicate location ID '%s' found (from file %s)", loc.ID, d.Name()))
				return nil
			}

            // *** Validate ThemeID before adding location ***
            if loc.ThemeID != "" {
                if _, themeExists := ws.themes[loc.ThemeID]; !themeExists {
                    loadErrors = append(loadErrors, fmt.Errorf("location '%s' (%s) references non-existent theme ID '%s'", loc.Name, loc.ID, loc.ThemeID))
                    // Decide: skip location, use default theme, or allow load? Forcing validation is safer.
                    return nil // Skip loading this location if theme invalid
                }
            } else {
                 fmt.Printf("    Warning: Location '%s' (%s) has no ThemeID defined.\n", loc.Name, loc.ID)
                 // Assign a default theme ID? Or allow empty?
            }


			ws.locations[loc.ID] = &loc
            fmt.Printf("    Loaded location: %s (%s) with Theme: '%s'\n", loc.Name, loc.ID, loc.ThemeID)
		}
		return nil
	})
    if err != nil {
		loadErrors = append(loadErrors, fmt.Errorf("error walking location directory %s: %w", locationDir, err))
	}

	// --- Post-Load Validation (Adjacency checks) ---
	for _, loc := range ws.locations {
		for _, adjID := range loc.AdjacentIDs {
			if _, exists := ws.locations[adjID]; !exists {
				loadErrors = append(loadErrors, fmt.Errorf("location '%s' (%s) references non-existent adjacent location ID '%s'", loc.Name, loc.ID, adjID))
			}
		}
	}

	fmt.Printf("World data loading finished. Locations: %d, Themes: %d\n", len(ws.locations), len(ws.themes))

	if len(loadErrors) > 0 {
        // ... (error reporting as before) ...
		return errors.New("errors during world data loading")
	}

	return nil
}


// GetLocation remains the same
func (ws *InMemoryWorldSystem) GetLocation(locationID string) (*LocationNode, error) {
	ws.mu.RLock()
	defer ws.mu.RUnlock()
	loc, ok := ws.locations[locationID]
	if !ok {
		return nil, fmt.Errorf("location with ID '%s' not found", locationID)
	}
	return loc, nil
}

// GetTheme returns the simplified theme definition (mainly for backend use now).
func (ws *InMemoryWorldSystem) GetTheme(themeID string) (*ThemeDefinition, error) {
	ws.mu.RLock()
	defer ws.mu.RUnlock()
	theme, ok := ws.themes[themeID]
	if !ok {
		return nil, fmt.Errorf("theme definition with ID '%s' not found", themeID)
	}
	return theme, nil
}

// IsAdjacent remains the same
func (ws *InMemoryWorldSystem) IsAdjacent(currentLocationID, targetLocationID string) (bool, error) {
    // ... (implementation as before) ...
	ws.mu.RLock()
	defer ws.mu.RUnlock()

	currentLoc, ok := ws.locations[currentLocationID]
	if !ok {
		return false, fmt.Errorf("current location with ID '%s' not found", currentLocationID)
	}

	if _, ok := ws.locations[targetLocationID]; !ok {
		return false, fmt.Errorf("target location with ID '%s' not found", targetLocationID)
	}

	for _, adjID := range currentLoc.AdjacentIDs {
		if adjID == targetLocationID {
			return true, nil
		}
	}
	return false, nil
}


// GetAllLocationIDs remains the same
func (ws *InMemoryWorldSystem) GetAllLocationIDs() []string {
	// ... (implementation as before) ...
	ws.mu.RLock()
	defer ws.mu.RUnlock()
	ids := make([]string, 0, len(ws.locations))
	for id := range ws.locations {
		ids = append(ids, id)
	}
	return ids
}


// GetAllThemeIDs remains the same
func (ws *InMemoryWorldSystem) GetAllThemeIDs() []string {
	// ... (implementation as before) ...
	ws.mu.RLock()
	defer ws.mu.RUnlock()
	ids := make([]string, 0, len(ws.themes))
	for id := range ws.themes {
		ids = append(ids, id)
	}
	return ids
}


// ValidateThemeExists checks if a theme ID is known to the system.
func (ws *InMemoryWorldSystem) ValidateThemeExists(themeID string) bool {
    ws.mu.RLock()
    defer ws.mu.RUnlock()
    _, exists := ws.themes[themeID]
    return exists
}

func (ws *InMemoryWorldSystem) GetAdjacentLocations(locationID string) ([]*LocationNode, error) {
	currentLoc, err := ws.GetLocation(locationID) // Use the interface method GetLocation
	if err != nil {
		return nil, err // Location doesn't exist
	}

	adjacent := []*LocationNode{}
	ws.mu.RLock() // Lock for reading map
	defer ws.mu.RUnlock()

	for _, adjID := range currentLoc.AdjacentIDs {
		// Use internal map access here for efficiency since we have the lock,
        // or call ws.GetLocation again (which handles locking itself).
        // Calling GetLocation is cleaner but involves repeated locking. Let's use direct access.
		if loc, ok := ws.locations[adjID]; ok {
			adjacent = append(adjacent, loc)
		} else {
			// This case should ideally be caught during LoadWorldData validation
			fmt.Printf("Warning: Adjacency check found reference to non-existent location ID '%s' from '%s'.\n", adjID, locationID)
		}
	}
	return adjacent, nil
}

