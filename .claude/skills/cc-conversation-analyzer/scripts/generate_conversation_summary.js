const fs = require('fs');
const path = require('path');

// Usage: node generate_conversation_summary.js <graph_file_path> [topics_analysis_path] [error_summary_path]
const GRAPH_FILE = process.argv[2];
const TOPICS_FILE = process.argv[3];
const ERROR_SUMMARY_FILE = process.argv[4];

if (!GRAPH_FILE || !fs.existsSync(GRAPH_FILE)) {
    console.error('❌ Please provide a valid path to a conversation graph JSON file.');
    console.error('Usage: node generate_conversation_summary.js <path_to_graph.json> [path_to_topics.json] [path_to_error_summary.csv]');
    process.exit(1);
}

console.log(`📊 Generating Summary for: ${path.basename(GRAPH_FILE)}\n`);

const graph = JSON.parse(fs.readFileSync(GRAPH_FILE, 'utf8'));
const conversations = graph.nodes.filter(n => n.type === 'conversation');

let topicsData = {};
if (TOPICS_FILE && fs.existsSync(TOPICS_FILE)) {
    console.log(`📘 Loading topics analysis from: ${path.basename(TOPICS_FILE)}`);
    topicsData = JSON.parse(fs.readFileSync(TOPICS_FILE, 'utf8'));
}

let errorStats = {};
if (ERROR_SUMMARY_FILE && fs.existsSync(ERROR_SUMMARY_FILE)) {
    console.log(`⚠️ Loading error summary from: ${path.basename(ERROR_SUMMARY_FILE)}`);
    const lines = fs.readFileSync(ERROR_SUMMARY_FILE, 'utf8').split('\n');
    // Skip header
    for (let i = 1; i < lines.length; i++) {
        const line = lines[i].trim();
        if (!line) continue;

        // Simple CSV parse (assuming no commas in filenames, but handling quotes in error msg)
        // Actually, we used quotes for fields with commas. We need a smarter split or just regex.
        // Let's use a regex to split by comma, ignoring commas inside quotes.
        const matches = line.match(/(".*?"|[^",\s]+)(?=\s*,|\s*$)/g);
        // This regex is a bit simple, might fail on some edge cases but usually works for simple CSVs.
        // Better approach: use a proper CSV parser or a robust split function.

        // Let's use a simpler approach: split by comma, but rejoin if inside quotes.
        // Or just use the file name as key which is the first column.

        // Since we know the structure: File,Total,Unique,MostFreq,Counts...
        // File is first. MostFreq is quoted if it has commas.

        // Let's just use a robust regex for CSV splitting
        const parts = [];
        let current = '';
        let inQuotes = false;
        for (let char of line) {
            if (char === '"') {
                inQuotes = !inQuotes;
            } else if (char === ',' && !inQuotes) {
                parts.push(current);
                current = '';
            } else {
                current += char;
            }
        }
        parts.push(current);

        if (parts.length >= 3) {
            const fileName = parts[0];
            errorStats[fileName] = {
                Total_Errors: parseInt(parts[1]) || 0,
                Unique_Errors: parseInt(parts[2]) || 0,
                Most_Frequent_Error: parts[3].replace(/^"|"$/g, '').replace(/""/g, '"') // Unquote
            };
        }
    }
}

// Build Resume chains from RESUMED_FROM edges
console.log('Building conversation chains (Resume & Clear)...');
const chainMap = new Map(); // rootId -> [convId, convId, ...]

// 1. Handle RESUMED_FROM (File linking)
// These edges link FILES, but we need to link CONVERSATIONS.
// The graph builder reuses the parent conversation ID for resume files.
// So, multiple files might share the SAME conversation ID.
// We need to find all files associated with a conversation ID.

// Actually, let's look at the graph structure we just built.
// If we reused the conversation ID, then 'conversations' array in graph.nodes 
// only contains the ROOT conversation node (because we didn't push new nodes for resumes).
// BUT, the stages from the resume files ARE in graph.nodes, and they point to that conversation ID.
// So, simply aggregating by conversation ID should work for Resume!

// However, we still have CLEARED_AFTER edges which create NEW conversation IDs.
// We need to link those.

// Find CLEARED_AFTER edges (from=parent, to=child)
const clearEdges = graph.edges.filter(e => e.type === 'CLEARED_AFTER');

// Build parent->child map for CLEARED_AFTER
const parentToChild = new Map();
clearEdges.forEach(edge => {
    if (!parentToChild.has(edge.from)) parentToChild.set(edge.from, []);
    parentToChild.get(edge.from).push(edge.to);
});

// Find roots (conversations with no incoming CLEARED_AFTER)
// Note: Resume files don't create new conversation IDs, so they don't affect this logic.
const allConvIds = new Set(conversations.map(c => c.id));
const children = new Set(clearEdges.map(e => e.to));
const roots = [...allConvIds].filter(id => !children.has(id));

// Build chains recursively
function buildChain(rootId) {
    const chain = [rootId];
    const queue = [rootId];

    while (queue.length > 0) {
        const current = queue.shift();
        const kids = parentToChild.get(current) || [];
        kids.forEach(kid => {
            chain.push(kid);
            queue.push(kid);
        });
    }

    return chain;
}

roots.forEach(rootId => {
    chainMap.set(rootId, buildChain(rootId));
});

console.log(`Found ${roots.length} root conversations`);

// Helper to format date
const fmtDate = (ts) => new Date(ts).toISOString().replace('T', ' ').substring(0, 19);

// Helper to get start/end time from stages
function getTimes(convId) {
    const stages = graph.nodes.filter(n => n.type === 'stage' && n.conversationId === convId);
    // We need to look at the entries in the file to get exact timestamps, 
    // but the graph nodes don't store raw entries to keep size down.
    // However, we can infer order from stage sequence.
    // For this summary, we'll use the file path to find the file if needed, 
    // OR we can just rely on the fact that we might need to re-read files for exact timestamps 
    // if they aren't in the node stats.

    // WAIT: The current graph structure stores 'stats' but not start/end timestamps on nodes.
    // We might need to update the builder to store timestamps, or read them now.
    // For now, let's assume we need to read the source file to get exact timestamps 
    // OR just list duration.

    // Actually, let's look at the graph data we have.
    // We have 'file' and 'startLine' / 'endLine'.
    // We can read the specific lines from the source file to get timestamps.
    return stages;
}

// We need to read source files to get timestamps since they aren't in the graph metadata yet.
const sourceFolder = graph.metadata.sourceFolder;

const summaryData = [];

console.log('Processing conversation chains...');

roots.forEach((rootId, idx) => {
    const chain = chainMap.get(rootId);
    const convNodes = chain.map(id => conversations.find(c => c.id === id));

    // Aggregate statistics across all segments in chain
    const totalDuration = convNodes.reduce((sum, c) => sum + c.stats.duration, 0);
    const totalUserMsgs = convNodes.reduce((sum, c) => sum + c.stats.userMessages, 0);
    const totalAsstMsgs = convNodes.reduce((sum, c) => sum + c.stats.assistantMessages, 0);
    const totalToolInt = convNodes.reduce((sum, c) => sum + c.stats.toolInteractions, 0);
    const totalStages = convNodes.reduce((sum, c) => sum + c.stats.stageCount, 0);
    const totalErrors = convNodes.reduce((sum, c) => sum + c.stats.errors, 0);

    // Collect all stages across the chain
    const allStages = [];
    convNodes.forEach(conv => {
        const stages = graph.nodes.filter(n => n.type === 'stage' && n.conversationId === conv.id);
        allStages.push(...stages);
    });

    allStages.sort((a, b) => {
        const seqA = parseInt(a.id.split('-')[3]);
        const seqB = parseInt(b.id.split('-')[3]);
        return seqA - seqB;
    });

    if (allStages.length === 0) return;

    const firstStage = allStages[0];
    const lastStage = allStages[allStages.length - 1];

    // Get timestamps from first and last stages
    let startTime = 'N/A';
    let endTime = 'N/A';

    try {
        const startFile = path.join(sourceFolder, firstStage.file);
        const startLines = fs.readFileSync(startFile, 'utf8').split('\n');

        for (const line of startLines) {
            try {
                const entry = JSON.parse(line);
                if (entry.timestamp) {
                    startTime = entry.timestamp;
                    break;
                }
                if (entry.snapshot && entry.snapshot.timestamp) {
                    startTime = entry.snapshot.timestamp;
                    break;
                }
            } catch (e) { }
        }

        const endFile = path.join(sourceFolder, lastStage.file);
        const endLines = fs.readFileSync(endFile, 'utf8').split('\n');

        for (let i = endLines.length - 1; i >= 0; i--) {
            try {
                const entry = JSON.parse(endLines[i]);
                if (entry.timestamp) {
                    endTime = entry.timestamp;
                    break;
                }
            } catch (e) { }
        }
    } catch (e) {
        // Ignore read errors
    }

    // Count unique agents across all stages in chain
    const agentEdges = graph.edges.filter(e =>
        e.type === 'SPAWNED_AGENT' && allStages.some(s => s.id === e.from)
    );
    const agentCount = agentEdges.length;

    // Use root conversation's analysis (category/topic)
    const rootConv = convNodes[0];

    // Extract Deep Analysis Data
    // We use the file name of the root conversation to look up the analysis
    // Note: The analysis JSON keys are file names (e.g., "file.jsonl.json" or just "file.json")
    // Our analysis keys are "file.jsonl.json" (from export_conversations.js)
    // But wait, export_conversations.js created files like "UUID.json".
    // The keys in topics_analysis.json are "UUID.json".
    // The rootConv.fileId is the UUID.
    const analysisKey = `${rootConv.fileId}.json`;
    const analysis = topicsData[analysisKey] || {};

    const deepTopics = analysis.topics ? analysis.topics.join(', ') : '';
    const deepSummary = analysis.summary || (analysis.error ? `Error: ${analysis.error}` : '');

    // Extract Error Stats
    // The error summary keys are also "UUID.json"
    const errorStat = errorStats[analysisKey] || { Total_Errors: 0, Unique_Errors: 0, Most_Frequent_Error: '' };

    summaryData.push({
        ID: rootId,
        Category: rootConv.analysis?.category || 'N/A',
        Topic: rootConv.analysis?.topic || 'N/A',
        File: rootConv.file,
        Start: startTime !== 'N/A' ? fmtDate(startTime) : 'N/A',
        End: endTime !== 'N/A' ? fmtDate(endTime) : 'N/A',
        DurationMin: totalDuration,
        Continuations: chain.length,
        Stages: totalStages,
        Agents: agentCount,
        UserMsgs: totalUserMsgs,
        AsstMsgs: totalAsstMsgs,
        ToolInt: totalToolInt,
        Errors: totalErrors, // From Graph (basic count)
        'Deep Topics': deepTopics,
        'AI Summary': deepSummary,
        'Detailed Error Count': errorStat.Total_Errors,
        'Unique Errors': errorStat.Unique_Errors,
        'Most Frequent Error': errorStat.Most_Frequent_Error
    });

    if ((idx + 1) % 50 === 0) process.stdout.write('.');
});

console.log('\n');

// Output Table
console.table(summaryData.slice(0, 20)); // Show first 20
if (summaryData.length > 20) console.log(`...and ${summaryData.length - 20} more conversations.`);

// Save to CSV
// Handle fields that might contain commas (like Summary) by wrapping in quotes
const csvHeader = Object.keys(summaryData[0]).join(',') + '\n';
const csvRows = summaryData.map(row => {
    return Object.values(row).map(val => {
        const str = String(val);
        if (str.includes(',') || str.includes('"') || str.includes('\n')) {
            return `"${str.replace(/"/g, '""')}"`;
        }
        return str;
    }).join(',');
}).join('\n');

const csvPath = GRAPH_FILE.replace('.json', '_summary.csv');

fs.writeFileSync(csvPath, csvHeader + csvRows);
console.log(`\n✅ Summary saved to: ${csvPath}`);
