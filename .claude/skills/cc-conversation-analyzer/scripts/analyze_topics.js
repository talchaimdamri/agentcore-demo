const fs = require('fs');
const path = require('path');
const https = require('https');

const queriesDir = process.argv[2];
const apiKey = process.env.GEMINI_API_KEY;

if (!queriesDir) {
    console.error('Please provide the path to the user_queries directory');
    process.exit(1);
}

if (!apiKey) {
    console.error('Please set the GEMINI_API_KEY environment variable');
    process.exit(1);
}

const outputDir = path.dirname(queriesDir);
const outputFile = path.join(outputDir, 'topics_analysis.json');

async function callGemini(text, retries = 3) {
    const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=${apiKey}`;


    // Truncate text if it's extremely long to avoid payload issues (approx 30k chars safe limit for simple JSON)
    // Gemini Flash has a huge context window, but let's be safe with the HTTP request body for now.
    const MAX_CHARS = 100000;
    const processedText = text.length > MAX_CHARS ? text.substring(0, MAX_CHARS) + "\n...[TRUNCATED]..." : text;

    const prompt = `
Analyze the following user queries from a coding session. Identify the main topics and intent.
Return a JSON object with the following structure:
{
  "topics": ["topic1", "topic2"],
  "summary": "Brief summary of what the user was trying to achieve."
}

User Queries:
${processedText}
`;

    const data = JSON.stringify({
        contents: [{
            parts: [{ text: prompt }]
        }],
        generationConfig: {
            responseMimeType: "application/json"
        }
    });

    for (let attempt = 1; attempt <= retries; attempt++) {
        try {
            return await new Promise((resolve, reject) => {
                const req = https.request(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Content-Length': Buffer.byteLength(data)
                    }
                }, (res) => {
                    let responseBody = '';
                    res.on('data', (chunk) => responseBody += chunk);
                    res.on('end', () => {
                        if (res.statusCode >= 200 && res.statusCode < 300) {
                            try {
                                const parsed = JSON.parse(responseBody);
                                if (!parsed.candidates || !parsed.candidates[0] || !parsed.candidates[0].content) {
                                    reject(new Error(`Unexpected API response structure: ${responseBody}`));
                                    return;
                                }
                                const content = parsed.candidates[0].content.parts[0].text;
                                resolve(JSON.parse(content));
                            } catch (e) {
                                reject(new Error(`Failed to parse response: ${e.message}, Body: ${responseBody}`));
                            }
                        } else {
                            const isRetryable = res.statusCode >= 500 || res.statusCode === 429;
                            const error = new Error(`API Error: ${res.statusCode} ${res.statusMessage} - ${responseBody}`);
                            error.isRetryable = isRetryable;
                            reject(error);
                        }
                    });
                });

                req.on('error', (e) => reject(e));
                req.write(data);
                req.end();
            });
        } catch (e) {
            if (attempt === retries || !e.isRetryable) {
                throw e;
            }
            console.log(`⚠️ Attempt ${attempt} failed (${e.message}). Retrying in ${attempt * 2}s...`);
            await new Promise(resolve => setTimeout(resolve, attempt * 2000));
        }
    }
}

async function main() {
    console.log(`📂 Reading queries from: ${queriesDir}`);

    const files = fs.readdirSync(queriesDir).filter(f => f.endsWith('.json'));
    console.log(`Found ${files.length} query files.`);

    const results = {};

    for (const file of files) {
        console.log(`Processing ${file}...`);
        const filePath = path.join(queriesDir, file);
        const queries = JSON.parse(fs.readFileSync(filePath, 'utf8'));

        const queryText = queries.map(q => `- [${q.timestamp}] ${q.content}`).join('\n');

        try {
            const analysis = await callGemini(queryText);
            results[file] = analysis;
            console.log(`✅ Analyzed ${file}:`, analysis.topics);
        } catch (e) {
            console.error(`❌ Error analyzing ${file}:`, e.message);
            results[file] = { error: e.message };
        }

        // Simple delay to be nice to the API
        await new Promise(resolve => setTimeout(resolve, 1000));
    }

    fs.writeFileSync(outputFile, JSON.stringify(results, null, 2));
    console.log(`💾 Saved analysis to ${outputFile}`);
}

main().catch(console.error);
