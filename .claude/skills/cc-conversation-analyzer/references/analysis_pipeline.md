# Analysis Pipeline Reference

Complete command sequence to run the Claude Code conversation analysis pipeline.

## Prerequisites

- Node.js installed
- `GEMINI_API_KEY` environment variable set (for topic and command analysis)

## Quick Start (Full Pipeline)

Run these commands in order. Scripts are located in `~/.claude/skills/cc-conversation-analyzer/scripts/`

```bash
# Set the skill scripts directory
SKILL_DIR="$HOME/.claude/skills/cc-conversation-analyzer/scripts"

# Set your Gemini API key (REQUIRED for topic/command analysis)
# If user doesn't have one, prompt: "Get a key at https://aistudio.google.com/apikey"
export GEMINI_API_KEY="your_key_here"

# Define your data folder (Claude Code project data)
# Usually at: ~/.claude/projects/<project-folder>
DATA_FOLDER="/path/to/.claude/projects/your-project"
OUTPUT_NAME="your-project-name"
```

### Step 1: Build Graph
```bash
node "$SKILL_DIR/build_conversation_graph.js" "$DATA_FOLDER"
# Output: analysis_results/$OUTPUT_NAME/conversation_graph.json
```

### Step 2: Export Conversations
```bash
node "$SKILL_DIR/export_conversations.js" "$DATA_FOLDER" "analysis_results/$OUTPUT_NAME/conversations"
```

### Step 3: Extract User Queries
```bash
node "$SKILL_DIR/extract_user_queries.js" "analysis_results/$OUTPUT_NAME/conversations" "analysis_results/$OUTPUT_NAME/user_queries"
```

### Step 4: Analyze Topics (Requires GEMINI_API_KEY)
```bash
node "$SKILL_DIR/analyze_topics.js" "analysis_results/$OUTPUT_NAME/user_queries"
# Output: analysis_results/$OUTPUT_NAME/topics_analysis.json
```

### Step 5: Analyze Errors
```bash
node "$SKILL_DIR/analyze_errors.js" "analysis_results/$OUTPUT_NAME/conversations"
# Output: error_analysis.csv, error_summary.csv
```

### Step 6: Analyze Risks
```bash
node "$SKILL_DIR/analyze_risks.js" "analysis_results/$OUTPUT_NAME/conversations"
# Output: risk_analysis.csv
```

### Step 7: Analyze Commands
```bash
node "$SKILL_DIR/analyze_commands.js" "analysis_results/$OUTPUT_NAME/conversations"
# Output: command_analysis_detailed.json
```

### Step 8: Generate Command Recommendations (Requires GEMINI_API_KEY)
```bash
node "$SKILL_DIR/recommend_commands.js" "analysis_results/$OUTPUT_NAME/command_analysis_detailed.json"
# Output: command_recommendations.md
```

### Step 9: Generate Final Summary
```bash
node "$SKILL_DIR/generate_conversation_summary.js" \
  "analysis_results/$OUTPUT_NAME/conversation_graph.json" \
  "analysis_results/$OUTPUT_NAME/topics_analysis.json" \
  "analysis_results/$OUTPUT_NAME/error_summary.csv"
# Output: conversation_graph_summary.csv
```

---

## Tool Reference

### 1. build_conversation_graph.js
**Purpose**: Transforms raw JSONL data into a structured graph.

**Node Types**:
- `conversation`: A distinct CC session
- `stage`: Context window segment (split by compaction/clear)
- `agent`: Spawned subagent

**Edge Types**:
- `HAS_STAGE`: Conversation contains stage
- `RESUMED_FROM`: File continues previous session
- `CLEARED_AFTER`: `/clear` command created new conversation
- `COMPACTED_INTO`: Context compaction created new stage
- `SPAWNED_AGENT`: Stage invoked a subagent

### 2. analyze_topics.js
**Purpose**: AI-powered topic identification using Gemini.

**Output Format**:
```json
{
  "file.json": {
    "topics": ["topic1", "topic2"],
    "summary": "Brief summary of user goals"
  }
}
```

### 3. analyze_errors.js
**Purpose**: Detect and categorize errors.

**Error Types**:
- System API Error
- Tool Execution Error
- Runtime Exception
- User Interruption
- Non-Zero Exit Code

**Outputs**:
- `error_analysis.csv`: Every error instance
- `error_summary.csv`: Aggregated per conversation

### 4. analyze_risks.js
**Purpose**: Detect sensitive data exposure.

**Risk Patterns**:
- AWS Access/Secret Keys
- Google API Keys
- OpenAI/Anthropic API Keys
- Stripe Live Keys
- Private Keys (PEM)
- Generic API keys/passwords

### 5. analyze_commands.js
**Purpose**: Track command success/failure rates.

**Groups commands by**:
- Base tool + action (e.g., `git commit`, `npm run`)
- Categorizes failure reasons

### 6. recommend_commands.js
**Purpose**: AI-generated fix recommendations.

**Criteria**: Commands with >= 4 failures AND > 15% failure rate.

### 7. generate_conversation_summary.js
**Purpose**: Aggregate all analysis into unified CSV.

**Columns**:
- ID, Category, Topic, File
- Start/End timestamps
- Duration, Continuations, Stages, Agents
- User/Assistant messages, Tool interactions
- Error counts, Deep Topics, AI Summary

---

## Expected Output Structure

```
analysis_results/<PROJECT>/
├── conversation_graph.json        # Core graph (nodes + edges)
├── conversation_graph_summary.csv # Human-readable summary
├── conversations/                 # Individual JSON exports
│   ├── uuid1.json
│   └── uuid2.json
├── user_queries/                  # Extracted user messages
│   ├── uuid1.json
│   └── uuid2.json
├── topics_analysis.json           # AI topic summaries
├── error_analysis.csv             # Detailed error log
├── error_summary.csv              # Per-conversation error counts
├── risk_analysis.csv              # Security findings
├── command_analysis_detailed.json # Command stats
└── command_recommendations.md     # AI fix suggestions
```
