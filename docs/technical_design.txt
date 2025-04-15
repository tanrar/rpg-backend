# Technical Architecture – llmrpg

## 1. High-Level Architecture

llmrpg is a modular, system-driven RPG engine that uses a large language model (LLM) to handle expressive narrative generation while a structured backend enforces consistent game logic, player state, and progression. The architecture is deliberately extensible — built to allow plug-and-play systems across various genres (RPG, strategy, etc.) while maintaining a narrative-first experience.

### 1.1 Core System Diagram (Conceptual)

```
+--------------------+ +--------------------+ +-------------------+
|                    | |                    | |                   |
| React Frontend     +<----->+ Go Backend/API +<----->+ LLM Server    |
|                    | |                    | | (OpenAI, etc.)   |
+--------------------+ +--------------------+ +-------------------+
        |                       |                      |
        |                       |                      |
        v                       v                      v
+--------------+    +----------------+    +------------------+
| UI Renderer  |    | Game Systems   |    | Prompt Builder   |
+--------------+    | (Narrative,    |    +------------------+
                    | Inventory,     |
                    | World, etc.)   |
                    +----------------+
```

### 1.2 Component Overview

#### **Frontend (React)**
- Scene display (narrative + visuals)
- Input field (typed or suggested actions)
- Panels for character sheet, inventory, world map (MVP)
- Theme-based CSS switching (via scene registry)

#### **Backend (Go / API layer)**
- Handles game state (player, inventory, world)
- Calls out to LLM via prompt builder
- Validates and applies LLM-provided actions
- Routes to other systems (combat, merchant) when triggered

#### **LLM Server (LLM of choice)**
- Receives structured prompts
- Returns narrative text + optional JSON actions
- Interprets ambiguous player input
- Limited to sandboxed, whitelisted system actions

### 1.3 System Modularity

All subsystems (inventory, combat, dialogue, quests, etc.) are implemented as discrete modules. Each has:
- Its own schema/model
- Optional frontend tab/panel
- A system name and identifier
- Optional `initiateScene` hook

> Example: The `combat` module isn't initialized in Phase 1, but later can register a `combatScene` renderer and action parser.

### 1.4 Data Flow (Narrative Loop)

```
[1] Player types or selects action ↓ 
[2] Frontend packages context + input ↓ 
[3] Backend builds prompt and sends to LLM ↓ 
[4] LLM returns narrative + optional actions ↓ 
[5] Backend validates actions, updates state ↓ 
[6] Frontend updates scene, UI, and panels
```

### 1.5 Storage & Persistence

- **In-memory** for active game sessions
- **Postgres (or similar)** for long-term save data
- **File-based registries** for:
  - Location definitions
  - Theme mappings
  - Item and ability definitions
- **Optional Redis** for caching recent interactions (especially useful for long sessions or multiplayer)

## 2. Narrative Scene System (Phase 1 Core)

### 2.1 Role

The Narrative Scene is the *primary gameplay view*. All player interaction during Phase 1 happens here. It's where the LLM presents narrative, the player responds, and the engine reacts.

> This is effectively your "main screen" — all gameplay loops back to this unless routed to a subscene.

### 2.2 Prompt Structure

**System Prompt** defines the rules:
- Response format
- Allowed actions (e.g. `updateLocation`, `addItem`)
- Setting/tone/lore constraints
- Examples of valid interactions

**Dynamic Prompt** includes:

```json
{
  "playerContext": {
    "name": "Ash",
    "class": "Psychic",
    "origin": "Wasteland-Born",
    "inventory": ["echo_key", "medkit"],
    "level": 2
  },
  "locationContext": {
    "id": "village_square",
    "description": "A cracked cobblestone square with flickering lights.",
    "theme": "sunlit_rural",
    "image": "village_square_day",
    "adjacentLocations": [
      { "id": "tavern", "name": "Old Tavern" },
      { "id": "forest_path", "name": "Path to the Forest" }
    ]
  },
  "sessionContext": {
    "timeElapsed": "2 hours",
    "recentActions": ["Spoke to hooded merchant", "Acquired echo key"]
  },
  "playerInput": "I walk into the tavern"
}
```

### 2.3 LLM Response Schema

The LLM is expected to respond in this format:

```json
{
  "narrative": "You enter the tavern. It smells of ash and boiled roots.",
  "suggestions": ["Talk to the barkeep", "Sit at a corner table", "Leave"],
  "actions": [
    {
      "type": "updateLocation",
      "data": {
        "locationId": "tavern_mainroom"
      }
    }
  ]
}
```

Note: The LLM is not required to return actions. Narrative-only responses are valid.

### 2.4 Action Whitelist & System Interface

In Phase 1, exposed actions are limited and registered globally:

| Action Type | Parameters | Description |
|-------------|------------|-------------|
| updateLocation | locationId | Triggers theme/image change |
| addItem | itemId, count | Adds item to inventory |
| removeItem | itemId, count | Removes item from inventory |
| applyEffect | effectId, duration, description | (Optional) Applies narrative condition |

Each action is parsed and dispatched to a backend system. If the system is not registered or the action is malformed, it is ignored or triggers a fallback response.

## 3. Character, Inventory, and Item Systems

### 3.1 Character System

The character system tracks all player-related data and is designed to be extensible without requiring combat or stat-based mechanics in Phase 1.

#### Core Character Data (MVP)

```go
type Character struct {
    ID           string            `json:"id"`
    Name         string            `json:"name"`
    Class        string            `json:"class"`         // e.g., "Psychic", "Courier"
    Origin       string            `json:"origin"`        // e.g., "Wasteland-Born"
    Level        int               `json:"level"`         // No stat changes in MVP
    Inventory    []InventoryItem   `json:"inventory"`     // Linked items
    Equipment    map[string]string `json:"equipment"`     // weapon, armor, etc. (optional for Phase 1)
    Flags        map[string]bool   `json:"flags"`         // Optional narrative tags
    Appearance   string            `json:"appearance"`    // (Optional) used in narrative prompts
}
```

This object is serialized and stored in the session. Inventory and equipment are updated by system calls or LLM actions.

### 3.2 Inventory System

Inventory is list-based and optionally typed by item categories.

#### Inventory Item Format

```go
type InventoryItem struct {
    ItemID   string `json:"itemId"`   // References item definition
    Count    int    `json:"count"`    // Number of copies
}
```

#### Item Definition Format

```go
type ItemDefinition struct {
    ID          string   `json:"id"`
    Name        string   `json:"name"`
    Description string   `json:"description"`
    Type        string   `json:"type"`        // e.g., "consumable", "quest", "exploration"
    Tags        []string `json:"tags"`        // e.g., ["healing", "flammable"]
    Usable      bool     `json:"usable"`      // Determines if LLM can suggest "use"
}
```

All items in inventory must refer to a static definition in a global ItemRegistry. This registry is loaded at runtime from a JSON or DB source.

### 3.3 Inventory System Interface

```go
type InventorySystem interface {
    GetInventory(playerID string) ([]InventoryItem, error)
    AddItem(playerID string, itemID string, count int) error
    RemoveItem(playerID string, itemID string, count int) error
    GetItemDefinition(itemID string) (ItemDefinition, error)
}
```

These methods are called by:

- The engine (for deterministic effects)
- The LLM processor (to resolve addItem/removeItem actions)
- The frontend (to display the character inventory tab)

### 3.4 Inventory Actions (LLM JSON Schema)

When the LLM returns item-related actions, they follow this format:

```json
{
  "type": "addItem",
  "data": {
    "itemId": "healing_vial",
    "count": 1
  }
}
```

OR

```json
{
  "type": "removeItem",
  "data": {
    "itemId": "scrap_metal",
    "count": 1
  }
}
```

These are parsed by the backend and routed to the InventorySystem.

### 3.5 Example LLM Item Use Response (Narrative-Only)

If the player types "I drink the vial", the LLM might return:

```json
{
  "narrative": "The liquid burns like fire, but your vision sharpens. You feel strangely alert.",
  "suggestions": ["Look around", "Continue down the path"]
}
```

No backend action occurs unless an action block is included. This allows narrative flavor without engine enforcement.

## 4. World System & Location Registry

### 4.1 Purpose

The **World System** defines the structural layout of the game world. Locations are stored in a hierarchical node-based model and linked via adjacency maps to enable player navigation and LLM reasoning.

The system serves:
- Prompt construction (LLM needs current + adjacent locations)
- Visual control (image and theme assignment)
- Exploration tracking (visit counts, discovered locations)
- Future expansion (region-based triggers, unlocks, encounters)

### 4.2 Hierarchical Model

```
Continent
└── Region
    └── Area
        └── Location
            └── Sub-Nodes (optional rooms/zones)
```

Nodes have parent-child relationships for scope and adjacency mappings for movement.

### 4.3 LocationNode Structure

```go
type LocationNode struct {
    ID             string                 `json:"id"`
    Name           string                 `json:"name"`
    Description    string                 `json:"description"`
    ParentID       string                 `json:"parentId,omitempty"`
    ChildrenIDs    []string               `json:"childrenIds,omitempty"`
    AdjacentIDs    []string               `json:"adjacentIds,omitempty"`
    Tags           []string               `json:"tags,omitempty"`      // e.g. ["indoors", "settlement"]
    ImageID        string                 `json:"imageId"`             // Scene art
    ThemeID        string                 `json:"themeId"`             // CSS/UI palette
    VisitCount     map[string]int         `json:"visitCount,omitempty"` // playerID → count
    Attributes     map[string]interface{} `json:"attributes,omitempty"` // flexible metadata
}
```

### 4.4 LocationTemplate

Used to procedurally create new nodes or spawn custom campaigns.

```go
type LocationTemplate struct {
    TemplateID      string                 `json:"templateId"`
    Name            string                 `json:"name"`
    Description     string                 `json:"description"`
    Type            string                 `json:"type"`        // e.g. "village", "forest", "tavern"
    DefaultThemeID  string                 `json:"defaultThemeId"`
    ChildTemplates  []string               `json:"childTemplates,omitempty"`
    ObjectTemplates []string               `json:"objectTemplates,omitempty"`
    NPCTemplates    []string               `json:"npcTemplates,omitempty"`
    Tags            []string               `json:"tags,omitempty"`
}
```

You can later plug this into deterministic world generation, campaign builders, or mod tools.

### 4.5 WorldSystem Interface

```go
type WorldSystem interface {
    GetCurrentLocation(playerID string) (LocationNode, error)
    MoveToLocation(playerID string, locationID string) error
    GetAdjacentLocations(locationID string) ([]LocationNode, error)
    GetLocationDefinition(locationID string) (LocationNode, error)
    MarkVisited(playerID string, locationID string) error
}
```

### 4.6 ThemeRegistry

Themes control visual tone via class-based UI elements. Each location uses a themeId to load one of these.

```go
type ThemeDefinition struct {
    ID        string `json:"id"`        // e.g., "sunlit_rural"
    Name      string `json:"name"`      // "Warm Countryside"
    CSSClass  string `json:"cssClass"`  // Used to dynamically switch UI
    Palette   map[string]string `json:"palette"` // Optional extra colors
}
```

Example:

```json
{
  "id": "frozen_ruins",
  "name": "Frozen Ruins",
  "cssClass": "theme-cold-blue",
  "palette": {
    "bg": "#1b2a33",
    "text": "#cce3f9",
    "accent": "#78c0f0"
  }
}
```

### 4.7 Example: LLM Location Prompt Context

This is what gets passed in every prompt:

```json
{
  "locationContext": {
    "currentLocation": {
      "id": "ruins_gate",
      "name": "Gate to the Frozen Ruins",
      "description": "Icy wind howls through the broken stones of an ancient gate.",
      "theme": "frozen_ruins",
      "image": "ruins_gate_cold"
    },
    "adjacentLocations": [
      { "id": "interior_sanctum", "name": "Sanctum Interior" },
      { "id": "return_path", "name": "Path Back to the Village" }
    ]
  }
}
```

The LLM can use this to narrate movement, suggest nearby paths, or update visuals using updateLocation.

### 4.8 Example Movement Action

Returned from the LLM and validated by backend:

```json
{
  "type": "updateLocation",
  "data": {
    "locationId": "interior_sanctum"
  }
}
```

Backend checks adjacency. If valid, moves the player and updates session state, triggering a new scene load and visual change.

## 5. LLM Prompt Engine & Action Execution Pipeline

### 5.1 Role of the Prompt Engine

The **Prompt Engine** constructs full context for every LLM call. It ensures:
- All required gameplay data is included
- The LLM understands its available capabilities
- Responses follow a standard structure
- Execution remains bounded by exposed systems

The Prompt Engine acts as a bridge between the game's internal state and the narrative model's storytelling layer.

### 5.2 System Prompt

The **system prompt** is a persistent set of instructions that tells the LLM how to behave. It includes:

- Role definition ("You are the narrative engine for a modular RPG…")
- Response format:
  ```json
  {
    "narrative": "string",
    "suggestions": ["action 1", "action 2"],
    "actions": [ { "type": "updateLocation", "data": {...} } ]
  }
  ```
- List of exposed action types and how they work
- Setting tone/lore style
- Formatting instructions
- Worldbuilding constraints (e.g. tech level, magic rules)

This is regenerated or re-used at session start and updated if systems change mid-game (e.g., combat becomes available).

### 5.3 Dynamic Prompt Assembly

Each LLM request is constructed from a combination of:

#### A. Player Context
```json
{
  "name": "Ash",
  "class": "Psychic",
  "origin": "Wasteland-Born",
  "level": 3,
  "inventory": ["medkit", "echo_key"],
  "equipment": { "weapon": "pulse_blade" }
}
```

#### B. Location & World Context
```json
{
  "currentLocation": {
    "id": "cathedral_gate",
    "description": "A towering gate sealed with ice. Faint blue light pulses beyond it.",
    "image": "cathedral_gate_frost",
    "theme": "frozen_ruins"
  },
  "adjacentLocations": [
    { "id": "inner_hall", "name": "Frozen Hall" },
    { "id": "return_path", "name": "Snowy Road" }
  ]
}
```

#### C. Session State
```json
{
  "timeElapsed": "3h17m",
  "recentActions": ["Examined frozen beacon", "Used Echo Key"]
}
```

#### D. Player Input
```json
{
  "playerInput": "I push the gate open"
}
```

All of this is serialized and embedded in a single API payload.

### 5.4 LLM Output Format (Standard)

```json
{
  "narrative": "The gate shudders, then yields to your will. Cold mist rolls outward.",
  "suggestions": ["Enter the hall", "Look back at the path", "Wait"],
  "actions": [
    {
      "type": "updateLocation",
      "data": { "locationId": "inner_hall" }
    }
  ]
}
```

### 5.5 Action Registry (Exposed Capabilities)

Each session exposes a limited set of allowable action types to the LLM. These are included in the system prompt and registered in the backend.

#### Example: MVP Action Definitions

```go
type ActionType string

const (
    UpdateLocation ActionType = "updateLocation"
    AddItem        ActionType = "addItem"
    RemoveItem     ActionType = "removeItem"
    ApplyEffect    ActionType = "applyEffect"
)
```

```go
type ExposedAction struct {
    Type        ActionType
    Description string
    Parameters  map[string]string // Name → type
    TargetSystem string           // System responsible (e.g. "World", "Inventory")
}
```

At runtime, this gets embedded in the system prompt as a declarative list of options the LLM can "call."

### 5.6 Backend Action Execution Pipeline

Actions returned from the LLM are parsed and routed to their target subsystems:

```go
func ExecuteLLMActions(actions []LLMAction, session Session) []ExecutionResult {
    var results []ExecutionResult

    for _, action := range actions {
        switch action.Type {
        case "updateLocation":
            result := WorldSystem.MoveToLocation(session.PlayerID, action.Data["locationId"])
            results = append(results, result)

        case "addItem":
            result := InventorySystem.AddItem(session.PlayerID, action.Data["itemId"], toInt(action.Data["count"]))
            results = append(results, result)

        case "removeItem":
            result := InventorySystem.RemoveItem(session.PlayerID, action.Data["itemId"], toInt(action.Data["count"]))
            results = append(results, result)

        case "applyEffect":
            result := CharacterSystem.ApplyEffect(session.PlayerID, action.Data)
            results = append(results, result)

        default:
            LogWarning("Unknown action type from LLM:", action.Type)
        }
    }

    return results
}
```

All actions are validated before being executed:
- Does the location exist?
- Is it adjacent?
- Is the item defined?
- Does the player have enough of it?

Invalid or malicious actions are safely ignored and logged.

### 5.7 Deterministic & Test Mode

A fallback version of the narrative engine can be run with no LLM calls, using:
- Static templates
- Rule-based responses
- Hardcoded scene transitions

This is useful for:
- Testing
- Offline mode
- Free tier support

All responses conform to the same format, allowing front- and back-end logic to remain consistent.

## 6. Extensibility Model & Scene Transition System

### 6.1 Core Idea

llmrpg is structured around **modular systems** that can be "plugged in" without altering the core engine. Each new gameplay feature (combat, merchant, quest journal, etc.) is its own scene, its own logic, and optionally, its own UI.

The narrative scene acts as a **router** — it sends players into these subsystems and receives them back when the scene ends.

### 6.2 Scene Types

```go
type SceneType string

const (
    NarrativeScene SceneType = "narrative"
    CombatScene    SceneType = "combat"
    DialogueScene  SceneType = "dialogue"
    ShopScene      SceneType = "shop"
    SkillScene     SceneType = "skill"
)
```

#### Scene Metadata

```go
type Scene struct {
    ID              string                 `json:"id"`
    Type            SceneType              `json:"type"`
    Title           string                 `json:"title"`
    Description     string                 `json:"description"`
    ParentScene     string                 `json:"parentScene,omitempty"`
    AllowedActions  []string               `json:"allowedActions"`
    ContextData     map[string]interface{} `json:"contextData"`
    UIState         map[string]interface{} `json:"uiState"`
    TransitionRules map[string][]string    `json:"transitionRules"`
}
```

Each scene is a stackable runtime context. When a system is entered (e.g., combat), the narrative scene is paused and pushed to a stack.

### 6.3 Transition Flow

```
[Narrative Scene]
      ↓
 LLM returns: {"action": "initiateCombat"}
      ↓
 Backend checks if "combat" system is registered
      ↓
 CombatScene is instantiated with initial data
      ↓
 Scene state is updated and UI re-renders
      ↓
 Player resolves combat
      ↓
 Control returns to NarrativeScene
```

The entire scene loop is runtime-stack based. Scenes can nest and unwind naturally.

### 6.4 SceneManager Interface

```go
type SceneManager interface {
    GetCurrentScene(playerID string) (*Scene, error)
    TransitionToScene(playerID string, newScene Scene) error
    ReturnToPreviousScene(playerID string) error
    UpdateSceneState(playerID string, updates map[string]interface{}) error
}
```

The SceneManager is system-agnostic. All it cares about is:
- What scene is running?
- What scene is next?
- Is this scene done?

### 6.5 System Registration

New systems are registered at engine boot (or dynamically in editor/dev mode):

```go
type GameSystem interface {
    GetName() string
    GetVersion() string
    Initialize(config map[string]interface{}) error
    Shutdown() error
    RegisterSceneTypes() []SceneType
    RegisterLLMActions() []string
    HandleAction(action LLMAction, session Session) error
}
```

Example: Combat system registers:
- SceneType = "combat"
- LLMActions = ["initiateCombat"]

Now the backend knows how to process initiateCombat if it's returned in the LLM response.

### 6.6 Dynamic Scene Control by LLM

Once registered, any valid scene can be triggered by LLM or the backend:

```json
{
  "action": "initiateCombat",
  "data": {
    "enemies": [
      { "id": "ice_sentinel", "count": 2 },
      { "id": "frost_wraith", "count": 1 }
    ],
    "environment": "cathedral_main_hall",
    "ambushState": "player_aware",
    "introText": "Ice cracks and shatters as shapes emerge from the stained glass."
  }
}
```

Backend dispatches to the combat module, which sets up the scene state, and pushes the CombatScene to the stack.

### 6.7 Example: Future Systems You Might Add

| System | Scene Type | LLM Actions | Requires UI? |
|--------|------------|-------------|-------------|
| Combat | combat | initiateCombat | ✅ |
| Merchant | shop | openShop | ✅ |
| NPC Dialogue | dialogue | startDialogue | ✅ (optional) |
| Skill Check | skill | initiateSkillCheck | ✅ |
| Journal | narrative | logDiscovery | ❌ (LLM only) |
| World Event | narrative | triggerWorldEvent | ❌ (engine-handled) |

All of these use the same interface and same scene management flow.

### 6.8 Error States & Fallbacks

If the LLM returns an action for a system that is not currently active:
- The action is logged
- The player receives a fallback narrative
- Optionally: developer-mode prompt includes a warning or stub message

Example fallback response:

```json
{
  "narrative": "You attempt to draw your weapon, but a strange force binds your limbs. Now is not the time for battle.",
  "suggestions": ["Retreat", "Look around"]
}
```

## 7. Persistence, Session State, and Save Structure

### 7.1 Overview

Persistence in llmrpg ensures that:
- Game progress is not lost between sessions
- Players can resume from any save point
- Systems like world state, inventory, flags, and visit history are retained
- Saves are modular, allowing phase-based expansion

All data is **JSON-serializable** and **schema-consistent**. Whether stored in Postgres, S3, or flat files, the structure remains the same.

### 7.2 Session Object

A `Session` represents one active or saved playthrough by a player.

```go
type Session struct {
    ID              string         `json:"id"`
    PlayerID        string         `json:"playerId"`
    Character       Character      `json:"character"`
    WorldState      WorldState     `json:"worldState"`
    CurrentScene    Scene          `json:"currentScene"`
    SceneHistory    []SceneRecord  `json:"sceneHistory"`
    CreatedAt       time.Time      `json:"createdAt"`
    LastActive      time.Time      `json:"lastActive"`
    Flags           map[string]bool `json:"flags"` // Optional narrative switches
    SaveSlot        string         `json:"saveSlot"` // e.g., "autosave", "manual1"
}
```

This is your root object. You can serialize and deserialize the entire game session from this one object.

### 7.3 Character Snapshot (Inline)

The Character object is embedded directly in the session. This includes:
- Class, origin, level
- Inventory and equipment
- Narrative flags
- Optional meta (e.g., "isCorrupted", "knowsAboutBeacon")

No external lookups are required for MVP — everything is self-contained.

### 7.4 WorldState

Represents the external world: locations, NPCs, events, discoveries.

```go
type WorldState struct {
    Regions           map[string]RegionState     `json:"regions"`
    VisitedLocations  map[string]int             `json:"visitedLocations"` // locationId → visit count
    DiscoveredLore    map[string]bool            `json:"discoveredLore"`
    GlobalFlags       map[string]interface{}     `json:"globalFlags"` // e.g., {"beacon_activated": true}
    FactionStandings  map[string]int             `json:"factionStandings"` // Optional future use
    TimeState         GameTime                   `json:"timeState"`
}
```

#### GameTime (Optional now)

```go
type GameTime struct {
    HoursElapsed   int    `json:"hoursElapsed"`
    LastTimestamp  string `json:"lastTimestamp"`
}
```

### 7.5 Scene History

Used for debugging, journaling, or narrative memory.

```go
type SceneRecord struct {
    SceneID     string    `json:"sceneId"`
    EnteredAt   time.Time `json:"enteredAt"`
    ExitedAt    time.Time `json:"exitedAt"`
    Summary     string    `json:"summary"`  // Optional LLM-generated blurb
}
```

Not required for core gameplay, but useful for: save-scumming detection, timeline display, ghost echo features, etc.

### 7.6 Save/Load API

All persistence runs through a unified backend service.

```go
type SessionStorage interface {
    SaveSession(session Session) error
    LoadSession(sessionID string) (Session, error)
    ListSaveSlots(playerID string) ([]string, error)
    DeleteSaveSlot(playerID string, slot string) error
}
```

### 7.7 Save Slots & Types

llmrpg supports:
- Autosave (at major transitions)
- Quick save/load
- Manual saves (multi-slot)
- Dev checkpoints (debug/QA)

Example save slots:

```json
["autosave", "manual1", "manual2", "quick", "debug-branch-a"]
```

Each slot maps to a Session in storage, stored as either:
- JSON blob (file system, cloud)
- Serialized DB row
- Hashed archive (for future secure/modded play)

### 7.8 Persistence Strategy Per System

| System | Stored In Session? | Notes |
|--------|-------------------|-------|
| Character | ✅ Yes | Self-contained, no external linkage |
| Inventory | ✅ Yes | Inline under character object |
| World State | ✅ Yes | Flat or nested map |
| Current Scene | ✅ Yes | Includes scene type + data |
| LLM History | ❌ Optional | Useful for regenerating LLM context |
| Summaries | ❌ Future | May be used for ghost journaling later |

### 7.9 Manual Save Format (Export)

Optional: support .llmsave export for local backup, modding, or browser-based restore.

```json
{
  "version": "1.0.0",
  "session": { ... full session payload ... },
  "exportedAt": "2025-04-15T17:42:00Z"
}
```

This allows:
- Offline backups
- Community sharing
- World-state mod injection (if allowed)

## 8. Development Strategy & Future Extensions

### 8.1 Philosophy: Modular First

The architecture of llmrpg is designed to:
- Isolate core systems (narrative, inventory, world)
- Allow optional plug-ins (combat, quests, shops)
- Enable setting swaps (sci-fi, fantasy, post-apoc, etc.)
- Separate narrative from mechanics wherever possible

This lets developers add or remove features without breaking the underlying structure — whether for testing, rapid prototyping, or full genre shifts.

### 8.2 Phase-Based Roadmap

llmrpg will be built in **discrete phases**, each focusing on a major system or layer of polish.

#### ✅ Phase 1: MVP – Narrative Core
- Narrative scene system (LLM-driven)
- Inventory and character basics
- World navigation (node-based)
- Theme and image mapping
- Save/load infrastructure

#### 🛠️ Phase 2: Core Interactivity
- Combat system (scene, UI, logic)
- Merchant/shop system
- Status effects + item abilities
- Dialogue scene routing

#### 🧠 Phase 3: Memory + World State
- NPC memory system
- Journal/logs
- Faction reputation
- Procedural location flags (e.g., danger, scarcity)

#### 🧩 Phase 4: Modularity & Tooling
- Scene/template editors
- Plugin registry and dynamic loading
- User-defined campaign support
- Optional mod API

#### 🌐 Phase 5+: Multiplayer & Advanced Systems
- Co-op or hotseat-style gameplay
- Shared world state and sync
- Timeline ghost runs / legacy echoes
- Experimental systems (SIN, corruption, dynamic bosses)

### 8.3 Testing Strategies

Every system should support both:
- **LLM-powered mode** (online, narrative-rich)
- **Deterministic fallback** (offline, rules-based)

This allows testing individual components (e.g. combat) without LLM calls. Use template-based scenes and rule validation to simulate behavior.

> You should be able to boot a “blank” narrative node that simulates a full run with no AI backend for test automation.

---

### 8.4 Debug Hooks

Each system includes developer switches:

| System     | Debug Features                             |
|------------|---------------------------------------------|
| LLM        | Log prompt/output, token cost, fallback text |
| Inventory  | Manual grant/remove UI                      |
| Scenes     | Force trigger by ID                         |
| World      | Teleport to location, reveal map            |
| Save       | Export current state, reload from blob      |

Enable these via:
- Developer mode toggle
- In-game console
- Special debug JSON actions

---

### 8.5 Extending Content (Safely)

To add new content or systems:
1. Register the new **SceneType**
2. Register the associated **LLM actions** (e.g., `initiateShop`)
3. Define the **handler logic** in the appropriate module
4. Update the **system prompt** if needed (to expose the action to LLM)
5. Optionally register **frontend views** (React components, tabs, etc.)

All additions should follow the same flow:
- Validate → Transition Scene → Return

This ensures:
- Scene consistency
- Save/load integrity
- Modular UI state
- Predictable routing

---

### 8.6 Recommended Dev Stack

| Layer        | Tech Stack               |
|--------------|--------------------------|
| Frontend     | React + Tailwind         |
| Backend      | Go + Echo/Fiber          |
| LLM Access   | OpenAI / local LLM proxy |
| DB           | Postgres / Redis         |
| File Storage | S3 / Local FS            |
| Testing      | Go test, JSON harnesses  |

---

### 8.7 Things to Avoid (For Now)

- No real-time gameplay (LLM doesn’t work that way)
- No player-vs-player yet (turn-based sync only)
- No deep branching quests until journaling is added
- No ghost/legacy systems until save format is finalized

---

### 8.8 Long-Term Goals

- A fully moddable, AI-powered narrative RPG engine
- Can support solo dev campaigns or large-scale storyworlds
- Plug-and-play genres and sub-systems
- Optional LLM-free builds for constrained environments
- Internal tool support for fast scene/setting creation

---

## Final Words

llmrpg is built on one core belief: **narrative is the genre**. Whether you're slinging plasma in space or arguing with a goblin king, the system lets stories emerge — dynamically, meaningfully, and replayably.

You can build a full game from just a few systems. You can rewrite the world by swapping the theme. The story lives here — and the engine is ready to tell it.

---

