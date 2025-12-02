const fs = require('fs');
const path = require('path');

// Usage: node build_conversation_graph.js <folder_path> [output_dir]
const FOLDER_PATH = process.argv[2];
const OUTPUT_DIR_ARG = process.argv[3];

if (!FOLDER_PATH) {
  console.error('❌ Usage: node build_conversation_graph.js <data_folder_path> [output_dir]');
  console.error('   data_folder_path: Path to Claude Code project data folder');
  console.error('   output_dir: (Optional) Output directory for analysis results');
  process.exit(1);
}

// Extract folder name for the output file
const folderName = path.basename(FOLDER_PATH).replace(/^-Users-.*-projects-/, '');

// Define Output Directory - use argument if provided, otherwise default to current working directory
const OUTPUT_DIR = OUTPUT_DIR_ARG || path.join(process.cwd(), 'analysis_results', folderName);
if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

const OUTPUT_FILE = path.join(OUTPUT_DIR, 'conversation_graph.json');

console.log('🔨 Building Conversation Graph (Methodology V3)\n');
console.log(`📁 Source: ${FOLDER_PATH}`);
console.log(`💾 Output: ${OUTPUT_FILE}\n`);

const graph = {
  metadata: {
    sourceFolder: FOLDER_PATH,
    analysisDate: new Date().toISOString(),
    methodology: "V3 (Gemini-Sonnet Hybrid)",
    stats: {
      files: 0,
      conversations: 0,
      stages: 0,
      agents: 0,
      compactingEvents: 0,
      clearEvents: 0
    }
  },
  nodes: [],
  edges: []
};

// Helper: Read and parse JSONL file
function readJSONL(filePath) {
  try {
    const content = fs.readFileSync(filePath, 'utf8');
    const lines = content.trim().split('\n').filter(l => l.trim());
    return lines.map((line, idx) => {
      try {
        const data = JSON.parse(line);
        return { ...data, _lineNum: idx + 1 };
      } catch (e) {
        return null;
      }
    }).filter(e => e !== null);
  } catch (error) {
    return [];
  }
}

// Helper: Get timestamp from entry
function getTimestamp(entry) {
  if (entry.timestamp) return new Date(entry.timestamp);
  if (entry.snapshot && entry.snapshot.timestamp) return new Date(entry.snapshot.timestamp);
  return null;
}

// Helper: Calculate duration
function calculateDuration(entries) {
  if (entries.length < 2) return 0;

  let first = null;
  let last = null;

  // Find first valid timestamp
  for (const entry of entries) {
    const ts = getTimestamp(entry);
    if (ts) {
      first = ts;
      break;
    }
  }

  // Find last valid timestamp
  for (let i = entries.length - 1; i >= 0; i--) {
    const ts = getTimestamp(entries[i]);
    if (ts) {
      last = ts;
      break;
    }
  }

  if (!first || !last) return 0;

  return Math.round((last - first) / 1000 / 60); // minutes
}

// Helper: Count refined metrics
function countMetrics(entries) {
  const stats = {
    userMessages: 0,
    assistantMessages: 0,
    toolInteractions: 0,
    totalEvents: entries.length,
    errors: 0
  };

  entries.forEach(e => {
    // Count Errors
    const content = e.message?.content;
    const contentStr = typeof content === 'string' ? content : JSON.stringify(content || '');
    const contentLower = contentStr.toLowerCase();

    if (e.type === 'system' && e.subtype === 'api_error') stats.errors++;
    else if (contentLower.includes('exit code') && !contentLower.includes('exit code 0')) stats.errors++;

    // Count Message Types
    if (e.type === 'user') {
      if (e.toolUseResult) {
        stats.toolInteractions++;
      } else {
        stats.userMessages++;
      }
    } else if (e.type === 'assistant') {
      const content = e.message?.content || [];
      // If content is array and has tool_use, it's a tool interaction
      // Even if it has text (reasoning), we count it as tool interaction or maybe separate?
      // User requested "My interactions only". 
      // Let's count assistant text-only as assistantMessages.
      // If it has tool_use, it's toolInteractions.
      const hasToolUse = Array.isArray(content) && content.some(c => c.type === 'tool_use');

      if (hasToolUse) {
        stats.toolInteractions++;
      } else {
        stats.assistantMessages++;
      }
    }
  });

  return stats;
}

// Step 1: Get files
console.log('📂 Step 1: Reading files...');
const allFiles = fs.readdirSync(FOLDER_PATH).filter(f => f.endsWith('.jsonl'));
const regularFiles = allFiles.filter(f => !f.startsWith('agent-'));
const agentFiles = allFiles.filter(f => f.startsWith('agent-'));

graph.metadata.stats.files = allFiles.length;
console.log(`   Found ${allFiles.length} files (${regularFiles.length} regular, ${agentFiles.length} agents)\n`);

// Step 1.5: Build UUID Index & Collect Timestamps
console.log('🔗 Step 1.5: Building UUID index & Sorting files...');
const uuidToFileMap = new Map(); // uuid -> fileId
const fileTimestamps = new Map(); // fileId -> timestamp (ms)

regularFiles.forEach(file => {
  const fileId = file.replace('.jsonl', '');
  const filePath = path.join(FOLDER_PATH, file);
  const entries = readJSONL(filePath);

  // Index UUIDs
  entries.forEach(entry => {
    if (entry.uuid) {
      uuidToFileMap.set(entry.uuid, fileId);
    }
  });

  // Get Start Time
  let startTime = null;
  for (const entry of entries) {
    const ts = getTimestamp(entry);
    if (ts) {
      startTime = ts;
      break;
    }
  }

  if (startTime) {
    fileTimestamps.set(file, startTime.getTime());
  } else {
    fileTimestamps.set(file, 0); // Unknown time
  }
});

// Sort files chronologically
regularFiles.sort((a, b) => {
  return (fileTimestamps.get(a) || 0) - (fileTimestamps.get(b) || 0);
});

console.log(`   Indexed UUIDs and sorted ${regularFiles.length} files\n`);

// Step 2: Process Conversations & Stages
console.log('🔪 Step 2: Parsing conversations and stages...');

const fileMap = new Map(); // fileId -> { conversations: [], stages: [] }

regularFiles.forEach((file, idx) => {
  const fileId = file.replace('.jsonl', '');
  const filePath = path.join(FOLDER_PATH, file);
  const entries = readJSONL(filePath);

  if (entries.length === 0) return;

  // Check if this is a Resume file
  const isResume = entries.length > 0 &&
    entries[0].type === 'summary' &&
    entries[0].leafUuid;

  let convSeq = 0;
  let stageSeq = 0;
  let currentConvId = `conv-${fileId}-${convSeq}`;
  let currentStageId = `stage-${fileId}-${convSeq}-${stageSeq}`;
  let currentConvNode = null;

  if (isResume) {
    const leafUuid = entries[0].leafUuid;
    const parentFileId = uuidToFileMap.get(leafUuid);

    if (parentFileId) {
      // Find parent conversation (last conv in parent file)
      const parentConvs = graph.nodes.filter(n =>
        n.type === 'conversation' && n.fileId === parentFileId
      );

      if (parentConvs.length > 0) {
        const parentConv = parentConvs[parentConvs.length - 1];
        currentConvId = parentConv.id;
        convSeq = parentConv.seq;
        stageSeq = parentConv.stats.stageCount;
        currentConvNode = parentConv; // Reuse existing node

        // Create RESUMED_FROM edge
        graph.edges.push({
          from: parentFileId,
          to: fileId,
          type: 'RESUMED_FROM',
          leafUuid: leafUuid
        });
      } else {
        // Parent not found (maybe processed later or missing)
        // Fallback: Create new conversation but mark as "should be resume"
        currentConvNode = {
          id: currentConvId,
          type: 'conversation',
          file: file,
          fileId: fileId,
          seq: convSeq,
          stats: { duration: 0, userMessages: 0, assistantMessages: 0, toolInteractions: 0, totalEvents: 0, errors: 0, stageCount: 0 }
        };
        graph.nodes.push(currentConvNode);
        graph.metadata.stats.conversations++;
      }
    } else {
      // Parent UUID not found in any file (True Orphan)
      currentConvNode = {
        id: currentConvId,
        type: 'conversation',
        file: file,
        fileId: fileId,
        seq: convSeq,
        stats: { duration: 0, userMessages: 0, assistantMessages: 0, toolInteractions: 0, totalEvents: 0, errors: 0, stageCount: 0 }
      };
      graph.nodes.push(currentConvNode);
      graph.metadata.stats.conversations++;
    }
  } else {
    // Fresh Start
    currentConvNode = {
      id: currentConvId,
      type: 'conversation',
      file: file,
      fileId: fileId,
      seq: convSeq,
      stats: { duration: 0, userMessages: 0, assistantMessages: 0, toolInteractions: 0, totalEvents: 0, errors: 0, stageCount: 0 }
    };
    graph.nodes.push(currentConvNode);
    graph.metadata.stats.conversations++;
  }

  let stageStartIdx = 0;
  let currentStageEntries = [];

  // Iterate entries
  entries.forEach((entry, i) => {
    // Check for /clear (New Conversation)
    const isClear = entry.message?.content?.includes('<command-name>/clear</command-name>');

    // Check for Compacting (New Stage)
    const isCompact = entry.type === 'system' && entry.subtype === 'compact_boundary';

    if (isClear) {
      // 1. Close current stage
      finishStage(currentStageId, currentConvId, currentStageEntries, false);

      // 2. Close current conversation (stats update happens implicitly via aggregation later)

      // 3. Start NEW Conversation
      convSeq++;
      stageSeq = 0;
      currentConvId = `conv-${fileId}-${convSeq}`;

      // Link old conv -> new conv
      graph.edges.push({
        from: `conv-${fileId}-${convSeq - 1}`,
        to: currentConvId,
        type: 'CLEARED_AFTER',
        line: entry._lineNum
      });
      graph.metadata.stats.clearEvents++;

      currentConvNode = {
        id: currentConvId,
        type: 'conversation',
        file: file,
        fileId: fileId,
        seq: convSeq,
        stats: { duration: 0, userMessages: 0, assistantMessages: 0, toolInteractions: 0, totalEvents: 0, errors: 0, stageCount: 0 }
      };
      graph.nodes.push(currentConvNode);
      graph.metadata.stats.conversations++;

      // 4. Start NEW Stage
      currentStageId = `stage-${fileId}-${convSeq}-${stageSeq}`;
      currentStageEntries = [];
      stageStartIdx = i + 1;

    } else if (isCompact) {
      // 1. Close current stage
      finishStage(currentStageId, currentConvId, currentStageEntries, true, entry);

      // 2. Start NEW Stage (Same Conversation)
      const oldStageId = currentStageId;
      stageSeq++;
      currentStageId = `stage-${fileId}-${convSeq}-${stageSeq}`;

      // Link stages
      graph.edges.push({
        from: oldStageId,
        to: currentStageId,
        type: 'COMPACTED_INTO',
        trigger: entry.compactMetadata?.trigger,
        tokens: entry.compactMetadata?.preTokens
      });
      graph.metadata.stats.compactingEvents++;

      currentStageEntries = [];
      stageStartIdx = i + 1;

    } else if (entry.type !== 'queue-operation') {
      // Add to current stage (ignoring queue-ops)
      currentStageEntries.push(entry);
    }
  });

  // Finish last stage
  finishStage(currentStageId, currentConvId, currentStageEntries, false);

  // Helper to close a stage
  function finishStage(stageId, convId, entries, compacted, compactEvent = null) {
    if (entries.length === 0 && !compacted) return; // Skip empty trailing stages

    const duration = calculateDuration(entries);
    const metrics = countMetrics(entries);

    const stageNode = {
      id: stageId,
      type: 'stage',
      conversationId: convId,
      file: file,
      stats: {
        duration,
        ...metrics
      },
      compacted: compacted,
      compactEvent: compactEvent
    };

    graph.nodes.push(stageNode);
    graph.metadata.stats.stages++;

    // Link Conv -> Stage
    graph.edges.push({
      from: convId,
      to: stageId,
      type: 'HAS_STAGE'
    });

    // Update Conv stats
    const convNode = graph.nodes.find(n => n.id === convId);
    if (convNode) {
      convNode.stats.duration += duration;
      convNode.stats.userMessages += metrics.userMessages;
      convNode.stats.assistantMessages += metrics.assistantMessages;
      convNode.stats.toolInteractions += metrics.toolInteractions;
      convNode.stats.totalEvents += metrics.totalEvents;
      convNode.stats.errors += metrics.errors;
      convNode.stats.stageCount++;
    }

    // Store for agent linking
    if (!fileMap.has(fileId)) fileMap.set(fileId, []);
    fileMap.get(fileId).push({ id: stageId, entries: entries });
  }

  if ((idx + 1) % 20 === 0) console.log(`   Processed ${idx + 1}/${regularFiles.length} files...`);
});

console.log(`   ✅ Created ${graph.metadata.stats.conversations} conversations, ${graph.metadata.stats.stages} stages\n`);

// Step 3: Agents
console.log('🤖 Step 3: Processing agents...');

agentFiles.forEach((file, idx) => {
  const agentId = file.replace('agent-', '').replace('.jsonl', '');
  const filePath = path.join(FOLDER_PATH, file);
  const entries = readJSONL(filePath);

  if (entries.length === 0) return;

  const parentSessionId = entries[0].sessionId; // Usually points to parent file UUID
  const metrics = countMetrics(entries);

  // Create Agent Node
  const agentNode = {
    id: `agent-${agentId}`,
    type: 'agent',
    file: file,
    agentId: agentId,
    stats: {
      duration: calculateDuration(entries),
      ...metrics
    }
  };
  graph.nodes.push(agentNode);
  graph.metadata.stats.agents++;

  // Link to Parent Stage
  // We need to find which STAGE in the parent file spawned this agent
  if (parentSessionId && fileMap.has(parentSessionId)) {
    const stages = fileMap.get(parentSessionId);

    // Find the tool_use result in the parent stages
    for (const stage of stages) {
      const toolResult = stage.entries.find(e =>
        e.type === 'user' && e.toolUseResult?.agentId === agentId
      );

      if (toolResult) {
        graph.edges.push({
          from: stage.id,
          to: agentNode.id,
          type: 'SPAWNED_AGENT',
          line: toolResult._lineNum
        });
        break; // Found the parent stage
      }
    }
  }

  if ((idx + 1) % 20 === 0) console.log(`   Processed ${idx + 1}/${agentFiles.length} agents...`);
});

console.log(`   ✅ Linked ${graph.metadata.stats.agents} agents\n`);

// Step 4: Save
console.log('💾 Step 4: Saving graph...');
fs.writeFileSync(OUTPUT_FILE, JSON.stringify(graph, null, 2));
console.log(`✅ Saved to ${OUTPUT_FILE}`);
console.log('\n📊 Final Stats:');
console.table(graph.metadata.stats);
