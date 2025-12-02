const fs = require('fs');
const path = require('path');

// Usage: node analyze_commands.js <conversations_folder>
const CONVERSATIONS_DIR = process.argv[2];

if (!CONVERSATIONS_DIR || !fs.existsSync(CONVERSATIONS_DIR)) {
    console.error('❌ Please provide a valid path to the conversations JSON folder.');
    process.exit(1);
}

const OUTPUT_FILE = path.join(path.dirname(CONVERSATIONS_DIR), 'command_analysis_detailed.json');

console.log(`🔍 Analyzing commands in: ${CONVERSATIONS_DIR}`);

const files = fs.readdirSync(CONVERSATIONS_DIR).filter(f => f.endsWith('.json'));
const commandStats = {};

// Helper to extract the "Core Intent" for grouping
function getCommandGroup(cmdStr) {
    // Remove "cd xyz && " prefixes just for the grouping key, but keep them in data
    const cleanCmd = cmdStr.replace(/^cd\s+\S+\s*(&&|;)\s*/, '').trim();

    const parts = cleanCmd.split(/\s+/);
    const baseTool = parts[0];

    if (['npm', 'pnpm', 'yarn', 'git', 'gcloud', 'terraform'].includes(baseTool)) {
        // Group by tool + action (e.g., "git commit", "npm run")
        return parts.length > 1 ? `${baseTool} ${parts[1]}` : baseTool;
    }
    return baseTool; // Fallback (e.g., "ls", "curl")
}

files.forEach((file, idx) => {
    const filePath = path.join(CONVERSATIONS_DIR, file);
    let events;
    try {
        events = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    } catch (err) { return; }

    const toolUseMap = {};

    // 1. Map Tool Uses
    events.forEach(e => {
        if (e.type === 'assistant' && e.message?.content) {
            e.message.content.forEach(block => {
                if (block.type === 'tool_use') toolUseMap[block.id] = block;
            });
        }
    });

    // 2. Process Results
    events.forEach(e => {
        if (e.type === 'user' && e.message?.content && Array.isArray(e.message.content)) {
            e.message.content.forEach(block => {
                if (block.type === 'tool_result') {
                    const toolUse = toolUseMap[block.tool_use_id];
                    if (toolUse && (toolUse.name === 'run_command' || toolUse.name === 'Bash')) {
                        const fullCommand = toolUse.input?.command;
                        if (!fullCommand) return;

                        // Use the simplified group for the main key
                        const groupKey = getCommandGroup(fullCommand);

                        if (!commandStats[groupKey]) {
                            commandStats[groupKey] = {
                                group: groupKey,
                                total: 0,
                                success: 0,
                                fail: 0,
                                // NEW: We store the detailed failure instances here
                                failed_instances: []
                            };
                        }

                        const stats = commandStats[groupKey];
                        stats.total++;

                        const isError = block.is_error || (typeof block.content === 'string' && block.content.includes('Exit code'));

                        if (isError) {
                            stats.fail++;
                            let errorMsg = typeof block.content === 'string' ? block.content : JSON.stringify(block.content);

                            // Categorize the error type
                            let reason = "Runtime Error";
                            if (errorMsg.includes("No such file or directory")) reason = "❌ Wrong Directory / Missing File";
                            else if (errorMsg.includes("command not found")) reason = "❌ Tool Missing";
                            else if (errorMsg.includes("User doesn't want to proceed")) reason = "🛑 User Interrupted";
                            else if (errorMsg.includes("syntax error")) reason = "⚠️ Syntax Error";

                            // Store the FULL original command with the error
                            stats.failed_instances.push({
                                full_command: fullCommand, // Keeps the 'cd', flags, everything
                                reason: reason,
                                output_snippet: errorMsg.substring(0, 300).replace(/\n/g, ' ')
                            });
                        } else {
                            stats.success++;
                        }
                    }
                }
            });
        }
    });
});

// Sort by most failures
const sorted = Object.values(commandStats).sort((a, b) => b.fail - a.fail);

fs.writeFileSync(OUTPUT_FILE, JSON.stringify(sorted, null, 2));
console.log(`✅ Detailed analysis saved to: ${OUTPUT_FILE}`);
