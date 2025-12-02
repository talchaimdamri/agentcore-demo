const fs = require('fs');
const path = require('path');
const https = require('https');

// Usage: node recommend_commands.js <command_analysis_detailed.json>
const ANALYSIS_FILE = process.argv[2];
const apiKey = process.env.GEMINI_API_KEY;

if (!ANALYSIS_FILE || !fs.existsSync(ANALYSIS_FILE)) {
    console.error('❌ Please provide a valid path to command_analysis_detailed.json');
    process.exit(1);
}

if (!apiKey) {
    console.error('❌ Please set the GEMINI_API_KEY environment variable');
    process.exit(1);
}

const OUTPUT_FILE = path.join(path.dirname(ANALYSIS_FILE), 'command_recommendations.md');
const analysis = JSON.parse(fs.readFileSync(ANALYSIS_FILE, 'utf8'));

// Filter for commands with >= 4 failures AND > 15% failure rate
const problematicCommands = analysis.filter(c => {
    const failRate = c.fail / c.total;
    return c.fail >= 4 && failRate > 0.15;
}).sort((a, b) => b.fail - a.fail).slice(0, 10);

if (problematicCommands.length === 0) {
    console.log('✅ No commands met the failure criteria (>= 4 fails and > 15% rate).');
    process.exit(0);
}

console.log(`🤖 Generating recommendations for top ${problematicCommands.length} failing command groups...`);

async function callGemini(prompt, retries = 3) {
    const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apiKey}`;

    const data = JSON.stringify({
        contents: [{ parts: [{ text: prompt }] }]
    });

    for (let attempt = 1; attempt <= retries; attempt++) {
        try {
            return await new Promise((resolve, reject) => {
                const req = https.request(url, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                }, (res) => {
                    let body = '';
                    res.on('data', chunk => body += chunk);
                    res.on('end', () => {
                        if (res.statusCode >= 200 && res.statusCode < 300) {
                            const parsed = JSON.parse(body);
                            resolve(parsed.candidates[0].content.parts[0].text);
                        } else {
                            reject(new Error(`API Error: ${res.statusCode} - ${body}`));
                        }
                    });
                });
                req.on('error', reject);
                req.write(data);
                req.end();
            });
        } catch (e) {
            if (attempt === retries) throw e;
            await new Promise(r => setTimeout(r, 1000 * attempt));
        }
    }
}

async function main() {
    let markdownReport = '# Command Execution Recommendations\n\n';
    markdownReport += 'This report analyzes the most frequent command failures (>= 4 fails, > 15% rate) and provides focused recommendations.\n\n';

    for (const cmd of problematicCommands) {
        console.log(`Processing Group: ${cmd.group}...`);

        // Extract unique error reasons and snippets - increased limit to 10 to provide more context
        const uniqueErrors = [...new Set(cmd.failed_instances.map(i => `${i.reason}: ${i.output_snippet}`))].slice(0, 10);
        const uniqueCommands = [...new Set(cmd.failed_instances.map(i => i.full_command))].slice(0, 5);
        const failRate = ((cmd.fail / cmd.total) * 100).toFixed(1);

        const prompt = `
        You are a DevOps and Tooling expert. Analyze the command failures below.

        **Command Group:** \`${cmd.group}\`
        **Stats:** ${cmd.fail} failures / ${cmd.total} runs (${failRate}% failure rate).

        **Failing Command Examples:**
        ${uniqueCommands.map(c => `- \`${c}\``).join('\n')}

        **Error Context (Reasons & Snippets):**
        ${uniqueErrors.map(e => `- ${e}`).join('\n')}

        **Task:**
        Provide a **very concise** recommendation (maximum 3-4 sentences total).
        1. Identify the primary cause of failure.
        2. Suggest the specific fix or alternative command.
        Do not use bullet points unless necessary. Be direct and actionable.
        `;

        try {
            const recommendation = await callGemini(prompt);
            markdownReport += `## Group: \`${cmd.group}\`\n`;
            markdownReport += `**Failures:** ${cmd.fail}/${cmd.total} (${failRate}%)\n\n`;
            markdownReport += recommendation + '\n\n---\n\n';
        } catch (err) {
            console.error(`Failed to get recommendation for ${cmd.group}:`, err.message);
            markdownReport += `## Group: \`${cmd.group}\`\n\n(Analysis Failed: ${err.message})\n\n---\n\n`;
        }

        // Rate limit pause
        await new Promise(r => setTimeout(r, 2000));
    }

    fs.writeFileSync(OUTPUT_FILE, markdownReport);
    console.log(`✅ Recommendations saved to: ${OUTPUT_FILE}`);
}

main().catch(console.error);
