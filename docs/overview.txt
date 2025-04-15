# Game Design Overview – llmrpg

## Core Concept

llmrpg is a modular, narrative-driven RPG framework designed to tell rich, immersive stories in a consistent mechanical structure. The game is powered by a large language model (LLM) which acts as the primary storyteller, allowing for highly expressive exploration and interaction with the world. Players engage primarily through a centralized narrative scene, with additional systems like combat, merchants, and faction influence layered in as modular features.

The game focuses first and foremost on **exploration, immersion, and narrative agency** — mechanics support the storytelling, not the other way around.

---

## Design Pillars

- **LLM as Storyteller**: The LLM interprets player input, generates atmospheric narrative, and serves as a reactive, improvisational narrator. It does not enforce rules — the game engine does that.
- **Modular Core**: The game is built from clean, separable systems. Combat, inventory, dialogue, and world simulation are individual modules that can be enabled, replaced, or expanded over time.
- **Narrative-Centric Gameplay**: Player progression is driven by choices, interactions, and exploration. A typical game loop involves reading rich descriptions, selecting contextual actions, and watching the world react.
- **Minimal UI, Maximum Meaning**: Static backgrounds, CSS-style themes, and clean menus reinforce immersion without clutter.
- **Setting-Agnostic System**: While the current build uses a dark sci-fi setting, the engine is modular enough to support alternate genres — from fantasy to post-apocalypse, from Star Trek to grand strategy. Change the systems, not the soul.

---

## Setting & Tone

The initial setting is a **grimdark sci-fi world**, where the boundaries between life and death are blurred by technology and corruption. The tone is atmospheric, melancholic, and strange — but the system is setting-agnostic. Everything from medieval fantasy to post-apocalyptic survival can be supported via modular definitions.

> Example: Adding a **starship module** could transform the game into a Star Trek-like RPG. Adding a **faction diplomacy system** could support a grand strategy campaign. The core remains the same: narrative-first gameplay.

---

## Core Gameplay Loop (Phase 1 MVP)

1. **Narrative Exploration**
   - The player reads rich text describing their location, situation, and environment.
   - The LLM provides narrative output and suggested actions.
2. **Decision-Making**
   - Players select or type actions.
   - The LLM interprets input and may return both narrative consequences and structured system actions (e.g., move location, give item).
3. **World & State Update**
   - The engine updates game state (location, inventory, character, etc.).
   - UI and scene image/theme update accordingly.
4. **Continue Narrative**
   - New prompt is sent to the LLM with updated context.
   - Loop continues.

---

## Example: MVP Gameplay Moment

This is what a typical scene might look like using only MVP systems (no combat, quests, or advanced systems yet):

---

**[Scene Image: dusty_village_gate.jpg]**  
**[UI Theme: warm_sunset]**

**Narrative:**  
You arrive at the outskirts of a crumbling village. A rusted sign leans at an angle, half-swallowed by the dust. A lone figure watches you from the shadows of a collapsed watchtower.

**Suggested Actions:**  
- Enter the village  
- Call out to the figure  
- Examine the surroundings

**Player (typed input):**  
“I approach the figure.”

**Narrative:**  
The figure steps forward, a woman wrapped in patchwork robes and carrying a steel-tipped staff. Her voice is rasped by the wind. “Not many make it out of the wastes. You got supplies to trade?”

**Suggested Actions:**  
- “What are you offering?”  
- “I have nothing for you.”  
- Walk past her and enter the village

**Player (typed input):**  
“Show me what you’ve got.”

**Narrative:**  
She opens a worn satchel, revealing vials of red liquid and a cracked device that hums faintly. “Old blood. And something that used to be useful.”

**Actions:**  
```json
[
  {
    "type": "addItem",
    "data": {
      "itemId": "healing_vial",
      "count": 1
    }
  },
  {
    "type": "removeItem",
    "data": {
      "itemId": "scrap_metal",
      "count": 1
    }
  }
]
```

Game Engine updates inventory:

- You receive 1x Healing Vial
- You lose 1x Scrap Metal

**Narrative:**  
The exchange is brief. She nods once, then disappears into the ruins behind the tower.

**Suggested Actions:**

- Enter the village
- Check your inventory
- Head toward the hills

---

## Feature Modularity

Features are organized into independent modules, each with clear integration points and optional activation.

| Feature            | Included in MVP | Can Be Replaced/Expanded? | Notes                                 |
|--------------------|:--------------:|:------------------------:|---------------------------------------|
| Narrative Scene    | Yes            | Yes                      | Central to all gameplay               |
| Inventory          | Yes            | Yes                      | Used by multiple systems              |
| Character Sheet    | Yes            | Yes                      | Base for abilities, origin, class     |
| Combat             | No (Phase 2+)  | Yes                      | Plug-in system, not core to engine    |
| Merchant System    | No (Phase 2+)  | Yes                      | Can be simulated via LLM until formalized |
| Quest Log / Journal| No             | Yes                      | Future addition, possibly LLM-authored|
| NPC System         | No             | Yes                      | World-state-aware, tracks relationships|
| Faction System     | No             | Yes                      | Tracks regional/global influence      |
| Exploration Items  | Yes (basic)    | Yes                      | Rope, torches, etc. influence scenes  |
| Themes & Visuals   | Yes            | Yes                      | Controlled via location registry      |

---

## MVP Goals

The MVP will include:

- Narrative system with structured prompt/response flow
- Character system (basic stats and inventory)
- Inventory (add/remove items, simple UI)
- Hierarchical world model with adjacent location data
- Theme/image registry to drive dynamic UI changes

These systems form the foundation of all future content.

---

## Future Vision

Once the core loop is stable, the game can evolve in multiple directions:

- Add modular combat, turning the experience into a tactical RPG
- Add legacy systems and world persistence for roguelike runs
- Add networked multiplayer for cooperative storytelling
- Add mod tools for creating new campaigns, settings, or mechanics

The true strength of the system lies in its flexibility: everything builds on a solid narrative base.

---

## Closing Statement

This is a game where the narrative is the genre — a framework designed to tell your story, no matter the setting. Whether you're scavenging through the wreckage of a ruined moon or negotiating peace between alien empires, the engine adapts.

Your story lives here.