const fs = require('fs');
const path = require('path');

// Usage: node analyze_errors.js <conversations_folder>
const CONVERSATIONS_DIR = process.argv[2];

if (!CONVERSATIONS_DIR || !fs.existsSync(CONVERSATIONS_DIR)) {
    console.error('❌ Please provide a valid path to the conversations JSON folder.');
    process.exit(1);
}

const OUTPUT_FILE_DETAILED = path.join(path.dirname(CONVERSATIONS_DIR), 'error_analysis.csv');
const OUTPUT_FILE_SUMMARY = path.join(path.dirname(CONVERSATIONS_DIR), 'error_summary.csv');

console.log(`🔍 Analyzing errors in: ${CONVERSATIONS_DIR}`);

const files = fs.readdirSync(CONVERSATIONS_DIR).filter(f => f.endsWith('.json'));
const allErrors = [];
const conversationStats = {};

files.forEach((file, idx) => {
    const filePath = path.join(CONVERSATIONS_DIR, file);
    let events;
    try {
        events = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    } catch (err) {
        console.error(`Error parsing ${file}:`, err);
        return;
    }

    // Initialize stats for this conversation
    conversationStats[file] = {
        Total_Errors: 0,
        Unique_Errors: 0,
        Most_Frequent_Error: 'N/A',
        Count_System_API_Error: 0,
        Count_Tool_Execution_Error: 0,
        Count_Runtime_Exception: 0,
        Count_User_Interruption: 0,
        Count_Non_Zero_Exit_Code: 0,
        Error_Counts: {} // To track frequency of specific error messages
    };

    let currentContext = 'Start of conversation';

    events.forEach(e => {
        // 1. UPDATE CONTEXT
        if (e.type === 'user' && e.message?.content) {
            if (typeof e.message.content === 'string') {
                currentContext = `User: ${e.message.content}`;
            }
        } else if (e.type === 'assistant' && e.message?.content) {
            const toolBlock = e.message.content.find(c => c.type === 'tool_use');
            if (toolBlock) {
                const inputStr = JSON.stringify(toolBlock.input).substring(0, 100);
                currentContext = `Tool Run: ${toolBlock.name} (${inputStr}...)`;
            }
        }

        // 2. DETECT ERRORS
        let errorFound = false;
        let errorType = '';
        let errorDetail = '';

        // Check A: System API Errors
        if (e.type === 'system' && e.subtype === 'api_error') {
            errorFound = true;
            errorType = 'System API Error';
            errorDetail = JSON.stringify(e.error || 'Unknown');
        }

        // Check B: Structured Tool Results
        if (e.toolUseResult && (e.toolUseResult.exitCode !== 0 && e.toolUseResult.exitCode != null)) {
            errorFound = true;
            errorType = 'Non-Zero Exit Code';
            errorDetail = `Exit Code: ${e.toolUseResult.exitCode} | Stderr: ${(e.toolUseResult.stderr || '').substring(0, 150)}`;
        }

        // Check C: Message Content
        if (e.type === 'user' && Array.isArray(e.message?.content)) {
            e.message.content.forEach(block => {
                if (block.type === 'tool_result' && block.is_error) {
                    errorFound = true;
                    errorType = 'Tool Execution Error';
                    let contentStr = typeof block.content === 'string' ? block.content : JSON.stringify(block.content);

                    if (contentStr.includes("User doesn't want to proceed") || contentStr.includes("interrupted by user")) {
                        errorType = 'User Interruption';
                    }

                    errorDetail = contentStr.substring(0, 300);
                }
                else if (block.content && typeof block.content === 'string') {
                    if (block.content.includes('Traceback (most recent call last)') || block.content.includes('Error:')) {
                        errorFound = true;
                        errorType = 'Runtime Exception';
                        errorDetail = block.content.substring(0, 300);
                    }
                }
            });
        }

        if (errorFound) {
            const cleanErrorDetail = errorDetail.replace(/\n/g, ' ');

            // Add to detailed list
            allErrors.push({
                File: file,
                Timestamp: e.timestamp || 'N/A',
                Type: errorType,
                Error: cleanErrorDetail,
                Context: currentContext.replace(/\n/g, ' ')
            });

            // Update Stats
            const stats = conversationStats[file];
            stats.Total_Errors++;

            // Increment Type Count
            const typeKey = `Count_${errorType.replace(/ /g, '_')}`;
            if (stats[typeKey] !== undefined) {
                stats[typeKey]++;
            }

            // Track Frequency
            stats.Error_Counts[cleanErrorDetail] = (stats.Error_Counts[cleanErrorDetail] || 0) + 1;
        }
    });

    // Post-process stats for this conversation
    const stats = conversationStats[file];
    const uniqueErrors = Object.keys(stats.Error_Counts);
    stats.Unique_Errors = uniqueErrors.length;

    if (uniqueErrors.length > 0) {
        // Find most frequent
        stats.Most_Frequent_Error = uniqueErrors.reduce((a, b) => stats.Error_Counts[a] > stats.Error_Counts[b] ? a : b);
    }
});

// Output Detailed CSV
if (allErrors.length === 0) {
    console.log('✅ No errors found!');
} else {
    console.log(`\n⚠️  Found ${allErrors.length} total errors.`);

    const csvHeader = 'File,Timestamp,Type,Error,Context\n';
    const csvRows = allErrors.map(err => {
        const cleanError = `"${(err.Error || '').replace(/"/g, '""')}"`;
        const cleanContext = `"${(err.Context || '').replace(/"/g, '""')}"`;
        return `${err.File},${err.Timestamp},${err.Type},${cleanError},${cleanContext}`;
    }).join('\n');

    fs.writeFileSync(OUTPUT_FILE_DETAILED, csvHeader + csvRows);
    console.log(`✅ Detailed report saved to: ${OUTPUT_FILE_DETAILED}`);
}

// Output Summary CSV
const summaryRows = Object.keys(conversationStats).map(file => {
    const stats = conversationStats[file];
    // Only include conversations with errors? Or all? 
    // Let's include only those with errors to keep it clean, or all to show "clean" ones.
    // User asked for "how match error was from each kind", implying we want to see the breakdown.
    // Let's include all for completeness, but maybe filter in the CSV viewer.
    // Actually, usually interesting to see which had 0 errors too.

    if (stats.Total_Errors === 0) return null; // Skip 0 error files for cleaner report? 
    // User said "add summary for each convestion". I'll include only those with errors for now to focus on the problem areas.

    const cleanMostFreq = `"${(stats.Most_Frequent_Error || '').replace(/"/g, '""')}"`;

    return [
        file,
        stats.Total_Errors,
        stats.Unique_Errors,
        cleanMostFreq,
        stats.Count_System_API_Error,
        stats.Count_Tool_Execution_Error,
        stats.Count_Runtime_Exception,
        stats.Count_User_Interruption,
        stats.Count_Non_Zero_Exit_Code
    ].join(',');
}).filter(row => row !== null); // Filter out nulls

if (summaryRows.length > 0) {
    const summaryHeader = 'File,Total_Errors,Unique_Errors,Most_Frequent_Error,Count_System_API_Error,Count_Tool_Execution_Error,Count_Runtime_Exception,Count_User_Interruption,Count_Non_Zero_Exit_Code\n';
    fs.writeFileSync(OUTPUT_FILE_SUMMARY, summaryHeader + summaryRows.join('\n'));
    console.log(`✅ Summary report saved to: ${OUTPUT_FILE_SUMMARY}`);
}
