const fs = require('fs');
const path = require('path');

const conversationsDir = process.argv[2];

if (!conversationsDir) {
    console.error('Please provide the path to the conversations directory');
    process.exit(1);
}

const outputDir = path.join(path.dirname(conversationsDir), 'user_queries');

if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
}

function extractText(content) {
    if (typeof content === 'string') return content;
    if (Array.isArray(content)) {
        return content
            .filter(block => block.type === 'text')
            .map(block => block.text)
            .join('\n');
    }
    return '';
}

async function main() {
    console.log(`📂 Reading from: ${conversationsDir}`);
    console.log(`💾 Output to: ${outputDir}`);

    const files = fs.readdirSync(conversationsDir).filter(f => f.endsWith('.json'));
    console.log(`Found ${files.length} conversation files.`);

    for (const file of files) {
        const filePath = path.join(conversationsDir, file);
        const events = JSON.parse(fs.readFileSync(filePath, 'utf8'));

        const userQueries = events
            .filter(e => e.type === 'user' && e.message && e.message.role === 'user')
            .map(e => ({
                timestamp: e.timestamp,
                content: extractText(e.message.content)
            }))
            .filter(q => q.content.trim().length > 0);

        if (userQueries.length > 0) {
            const outputFile = path.join(outputDir, file);
            fs.writeFileSync(outputFile, JSON.stringify(userQueries, null, 2));
            console.log(`✅ Extracted ${userQueries.length} queries from ${file}`);
        } else {
            console.log(`⚠️ No user queries found in ${file}`);
        }
    }
}

main().catch(console.error);
