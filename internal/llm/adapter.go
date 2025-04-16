package llm

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time" // Added for http client timeout
	// We don't strictly need world/character imports here,
	// as PromptData uses simplified structures.
)

// --- Data Structures ---

// LLMAction represents a structured action the LLM wants the engine to perform.
type LLMAction struct {
	Type string                 `json:"type"`
	Data map[string]interface{} `json:"data"`
}

// LLMResponse is the structure returned by our adapter to the narrative engine.
type LLMResponse struct {
	Narrative   string      `json:"narrative"`
	Suggestions []string    `json:"suggestions,omitempty"`
	Actions     []LLMAction `json:"actions,omitempty"`
}

// --- Prompt Data Structures ---
// (Simplified context structs remain the same)
type PlayerContextData struct {
	Name   string `json:"name"`
	Class  string `json:"class,omitempty"`
	Origin string `json:"origin,omitempty"`
	Level  int    `json:"level"`
}

type LocationContextData struct {
	CurrentLocationName   string   `json:"currentLocationName"`
	CurrentLocationDesc   string   `json:"currentLocationDesc"`
	AdjacentLocationIDs   []string `json:"adjacentLocationIds"`
	AdjacentLocationNames []string `json:"adjacentLocationNames"`
	CurrentThemeID        string   `json:"currentThemeId,omitempty"`
}

type SessionContextData struct {
	TimeElapsed   string   `json:"timeElapsed,omitempty"`
	RecentActions []string `json:"recentActions,omitempty"`
}

type PromptData struct {
	PlayerContext   PlayerContextData   `json:"playerContext"`
	LocationContext LocationContextData `json:"locationContext"`
	SessionContext  SessionContextData  `json:"sessionContext,omitempty"`
	PlayerInput     string              `json:"playerInput"`
}

// --- LLM Adapter Interface ---

type Adapter interface {
	GenerateResponse(ctx context.Context, systemPrompt string, promptData PromptData) (*LLMResponse, error)
}

// --- Gemini Adapter Implementation (HTTP with JSON Mode) ---

// GeminiAdapter implements the Adapter interface using standard HTTP calls.
type GeminiAdapter struct {
	modelName   string
	httpClient  *http.Client
	apiEndpoint string
}

// NewGeminiAdapter creates a new Gemini adapter instance using HTTP.
func NewGeminiAdapter(modelName string) *GeminiAdapter {
	if modelName == "" {
		modelName = "gemini-1.5-flash-latest" // Default model supporting JSON mode
	}
	return &GeminiAdapter{
		modelName:   modelName,
		httpClient:  &http.Client{Timeout: 90 * time.Second}, // Increased timeout slightly
		apiEndpoint: "https://generativelanguage.googleapis.com/v1beta/models",
	}
}

// --- Internal Structs for Gemini API Request/Response ---

type geminiPart struct {
	Text string `json:"text"`
}

type geminiContent struct {
	Parts []geminiPart `json:"parts"`
	Role  string       `json:"role,omitempty"`
}

type geminiSafetySetting struct {
	Category  string `json:"category"`
	Threshold string `json:"threshold"`
}

type geminiGenerationConfig struct {
	Temperature     *float32 `json:"temperature,omitempty"`
	TopP            *float32 `json:"topP,omitempty"`
	TopK            *int     `json:"topK,omitempty"`
	MaxOutputTokens *int     `json:"maxOutputTokens,omitempty"`
	StopSequences   []string `json:"stopSequences,omitempty"`
	// *** Add responseMimeType for JSON Mode ***
	ResponseMimeType string `json:"responseMimeType,omitempty"`
	// Optional: Define responseSchema for stricter control later
	// ResponseSchema *geminiResponseSchema `json:"responseSchema,omitempty"`
}

// geminiRequest is the structure sent to the Gemini API generateContent endpoint
type geminiRequest struct {
	Contents         []geminiContent         `json:"contents"`
	SafetySettings   []geminiSafetySetting   `json:"safetySettings,omitempty"`
	GenerationConfig *geminiGenerationConfig `json:"generationConfig,omitempty"`
}

// --- Gemini API Response Structures ---

type geminiCandidate struct {
	Content       geminiContent        `json:"content"` // Content will contain the JSON string in parts[0].text
	FinishReason  string               `json:"finishReason,omitempty"`
	Index         int                  `json:"index"`
	SafetyRatings []geminiSafetyRating `json:"safetyRatings,omitempty"`
	TokenCount    int                  `json:"tokenCount,omitempty"`
}

type geminiSafetyRating struct {
	Category    string `json:"category"`
	Probability string `json:"probability"`
	Blocked     bool   `json:"blocked,omitempty"`
}

type geminiPromptFeedback struct {
	SafetyRatings []geminiSafetyRating `json:"safetyRatings,omitempty"`
	BlockReason   string               `json:"blockReason,omitempty"`
}

type geminiResponse struct {
	Candidates     []geminiCandidate     `json:"candidates"`
	PromptFeedback *geminiPromptFeedback `json:"promptFeedback,omitempty"`
	UsageMetadata  *geminiUsageMetadata  `json:"usageMetadata,omitempty"`
}

type geminiUsageMetadata struct {
	PromptTokenCount     int `json:"promptTokenCount"`
	CandidatesTokenCount int `json:"candidatesTokenCount"`
	TotalTokenCount      int `json:"totalTokenCount"`
}

// --- Expected JSON structure within the LLM's text response ---
// Define the structure we expect the LLM to generate when in JSON mode.
// This mirrors our internal LLMResponse but is used for parsing the LLM output.
type expectedLLMJsonOutput struct {
	Narrative   string      `json:"narrative"`             // Field for the story text
	Suggestions []string    `json:"suggestions,omitempty"` // Field for suggested actions
	Actions     []LLMAction `json:"actions,omitempty"`     // Field for game actions
	// Add any other fields the LLM might generate
}

// GenerateResponse makes a call to the Gemini API using standard HTTP, requesting JSON output.
func (g *GeminiAdapter) GenerateResponse(ctx context.Context, systemPrompt string, promptData PromptData) (*LLMResponse, error) {
	fmt.Println("--- GeminiAdapter: GenerateResponse Called (HTTP JSON Mode) ---")

	apiKey := os.Getenv("GEMINI_API_KEY")
	if apiKey == "" {
		return nil, fmt.Errorf("GEMINI_API_KEY environment variable not set")
	}

	// --- Construct Prompt ---
	// Combine system prompt and dynamic context + user input.
	// When using JSON mode, clearly instruct the LLM to populate specific fields
	// in the JSON output (narrative, suggestions, actions).
	var fullPromptBuilder strings.Builder
	if systemPrompt != "" {
		fullPromptBuilder.WriteString(systemPrompt)
		// Add specific instructions for JSON mode:
		fullPromptBuilder.WriteString("\n\nRespond ONLY with a valid JSON object containing 'narrative' (string), 'suggestions' (array of strings, optional), and 'actions' (array of action objects, optional) fields.")
		fullPromptBuilder.WriteString(" The 'narrative' should describe the current scene and outcome. Only include 'actions' if the player's input implies a specific game action like moving location.")
		fullPromptBuilder.WriteString("\n\n---\n\n") // Separator
	}
	// Add context (as before)
	fullPromptBuilder.WriteString(fmt.Sprintf("Current Location: %s (%s)\n", promptData.LocationContext.CurrentLocationName, promptData.LocationContext.CurrentLocationDesc))
	if len(promptData.LocationContext.AdjacentLocationNames) > 0 {
		fullPromptBuilder.WriteString(fmt.Sprintf("Nearby: %s\n", strings.Join(promptData.LocationContext.AdjacentLocationNames, ", ")))
	}
	if len(promptData.SessionContext.RecentActions) > 0 {
		fullPromptBuilder.WriteString(fmt.Sprintf("Recent Events: %s\n", strings.Join(promptData.SessionContext.RecentActions, "; ")))
	}
	fullPromptBuilder.WriteString(fmt.Sprintf("\nPlayer (%s - %s): %s", promptData.PlayerContext.Name, promptData.PlayerContext.Class, promptData.PlayerInput))

	// --- Log the final prompt ---
	finalPrompt := fullPromptBuilder.String()
	fmt.Printf("--- Final Prompt Sent to Gemini ---\n%s\n---------------------------------\n", finalPrompt)

	// --- Construct Request Body ---
	apiRequest := geminiRequest{
		Contents: []geminiContent{
			{
				Role: "user",
				Parts: []geminiPart{
					{Text: finalPrompt}, // Use the logged prompt string
				},
			},
		},
		// *** Configure JSON Mode ***
		GenerationConfig: &geminiGenerationConfig{
			ResponseMimeType: "application/json",
			// Optional: Add other generation parameters
			// Temperature: float32Ptr(0.8),
			// MaxOutputTokens: intPtr(2048),
		},
		// Optional: Add Safety Settings if needed
		// SafetySettings: []geminiSafetySetting{
		//     {Category: "HARM_CATEGORY_HARASSMENT", Threshold: "BLOCK_MEDIUM_AND_ABOVE"},
		//     // ... other categories
		// },
	}

	// --- Marshal Request Body ---
	reqBodyBytes, err := json.Marshal(apiRequest)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request body: %w", err)
	}
	// fmt.Printf("Request Body JSON:\n%s\n", string(reqBodyBytes)) // Debug logging

	// --- Prepare HTTP Request ---
	url := fmt.Sprintf("%s/%s:generateContent?key=%s", g.apiEndpoint, g.modelName, apiKey)
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewBuffer(reqBodyBytes))
	if err != nil {
		return nil, fmt.Errorf("failed to create HTTP request: %w", err)
	}
	httpReq.Header.Set("Content-Type", "application/json")

	// --- Execute HTTP Request ---
	fmt.Printf("Sending request to Gemini API (JSON Mode): %s...\n", url)
	httpResp, err := g.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("failed to execute HTTP request: %w", err)
	}
	defer httpResp.Body.Close()

	// --- Read Response Body ---
	respBodyBytes, err := io.ReadAll(httpResp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body: %w", err)
	}

	// --- Handle Non-200 Status Codes ---
	if httpResp.StatusCode != http.StatusOK { /* ... (error handling as before) ... */
		var apiError struct {
			Error struct {
				Code    int    `json:"code"`
				Message string `json:"message"`
				Status  string `json:"status"`
			} `json:"error"`
		}
		if json.Unmarshal(respBodyBytes, &apiError) == nil && apiError.Error.Message != "" {
			return nil, fmt.Errorf("gemini API request failed: status %d, code %d, message: %s", httpResp.StatusCode, apiError.Error.Code, apiError.Error.Message)
		}
		return nil, fmt.Errorf("gemini API request failed: status %s, body: %s", httpResp.Status, string(respBodyBytes))
	}

	// --- Unmarshal Gemini API Response ---
	var apiResponse geminiResponse
	if err := json.Unmarshal(respBodyBytes, &apiResponse); err != nil {
		fmt.Printf("Raw Response Body on Unmarshal Error:\n%s\n", string(respBodyBytes))
		return nil, fmt.Errorf("failed to unmarshal Gemini API response wrapper: %w", err)
	}
	// fmt.Printf("Parsed API Response Wrapper: %+v\n", apiResponse) // Debug logging

	// --- Check for Prompt Blocks ---
	if apiResponse.PromptFeedback != nil && apiResponse.PromptFeedback.BlockReason != "" { /* ... (error handling as before) ... */
		return nil, fmt.Errorf("prompt blocked by API: %s (Safety Ratings: %+v)", apiResponse.PromptFeedback.BlockReason, apiResponse.PromptFeedback.SafetyRatings)
	}

	// --- Extract and Parse the JSON Content from the Candidate ---
	if len(apiResponse.Candidates) == 0 || len(apiResponse.Candidates[0].Content.Parts) == 0 {
		// Handle cases where content generation might have been blocked or response is empty
		if len(apiResponse.Candidates) > 0 && apiResponse.Candidates[0].FinishReason == "SAFETY" {
			return nil, fmt.Errorf("content generation stopped due to safety settings: %+v", apiResponse.Candidates[0].SafetyRatings)
		}
		return nil, fmt.Errorf("gemini response missing expected content")
	}

	// The actual JSON output from the LLM is inside the text part
	llmOutputJsonString := apiResponse.Candidates[0].Content.Parts[0].Text
	// fmt.Printf("LLM Output JSON String:\n%s\n", llmOutputJsonString) // Debug logging

	// Unmarshal the JSON string generated by the LLM into our expected structure
	var parsedOutput expectedLLMJsonOutput
	if err := json.Unmarshal([]byte(llmOutputJsonString), &parsedOutput); err != nil {
		// Fallback: Return the raw string as narrative if parsing fails? Or return error?
		// Let's return an error for now, as structured output was expected.
		return nil, fmt.Errorf("failed to parse LLM's JSON output: %w. Raw output: %s", err, llmOutputJsonString)
	}

	// --- Map Parsed Output to internal LLMResponse ---
	llmResponse := &LLMResponse{
		Narrative:   parsedOutput.Narrative,   // Use the parsed narrative
		Suggestions: parsedOutput.Suggestions, // Use the parsed suggestions
		Actions:     parsedOutput.Actions,     // Use the parsed actions
	}

	// Log token usage if available
	if apiResponse.UsageMetadata != nil { /* ... (logging as before) ... */
		fmt.Printf("Gemini API Token Usage: Prompt=%d, Candidates=%d, Total=%d\n", apiResponse.UsageMetadata.PromptTokenCount, apiResponse.UsageMetadata.CandidatesTokenCount, apiResponse.UsageMetadata.TotalTokenCount)
	}

	fmt.Println("--- GeminiAdapter: Successfully Received and Parsed JSON Response ---")
	return llmResponse, nil
}

// --- Helper functions (optional pointer literals) ---
// func float32Ptr(v float32) *float32 { return &v }
// func intPtr(v int) *int             { return &v }
