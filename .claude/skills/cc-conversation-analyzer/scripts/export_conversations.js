const fs = require('fs');
const path = require('path');
const readline = require('readline');

const graphPath = process.argv[2];

if (!graphPath) {
    console.error('Please provide the path to conversation_graph.json');
    process.exit(1);
}

const graph = JSON.parse(fs.readFileSync(graphPath, 'utf8'));
const sourceFolder = graph.metadata.sourceFolder;
const outputDir = path.dirname(graphPath);
const conversationsDir = path.join(outputDir, 'conversations');

if (!fs.existsSync(conversationsDir)) {
    fs.mkdirSync(conversationsDir, { recursive: true });
}

async function processFile(filePath) {
    const fileStream = fs.createReadStream(filePath);
    const rl = readline.createInterface({
        input: fileStream,
        crlfDelay: Infinity
    });

    const events = [];
    for await (const line of rl) {
        if (line.trim()) {
            try {
                events.push(JSON.parse(line));
            } catch (e) {
                console.error(`Error parsing line in ${filePath}:`, e);
            }
        }
    }
    return events;
}

async function main() {
    console.log(`📂 Source Folder: ${sourceFolder}`);
    console.log(`💾 Output Folder: ${conversationsDir}`);

    const conversations = graph.nodes.filter(n => n.type === 'conversation');
    console.log(`Found ${conversations.length} conversations to process.`);

    for (const conv of conversations) {
        const sourceFile = path.join(sourceFolder, conv.file);
        const outputFile = path.join(conversationsDir, `${conv.fileId}.json`);

        if (fs.existsSync(sourceFile)) {
            const events = await processFile(sourceFile);
            fs.writeFileSync(outputFile, JSON.stringify(events, null, 2));
            console.log(`✅ Exported ${conv.fileId}.json (${events.length} events)`);
        } else {
            console.warn(`⚠️ Source file not found: ${sourceFile}`);
        }
    }
}

main().catch(console.error);
