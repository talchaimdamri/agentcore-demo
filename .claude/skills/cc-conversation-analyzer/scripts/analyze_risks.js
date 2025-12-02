const fs = require('fs');
const path = require('path');

// Usage: node analyze_risks.js <conversations_folder>
const CONVERSATIONS_DIR = process.argv[2];

if (!CONVERSATIONS_DIR || !fs.existsSync(CONVERSATIONS_DIR)) {
    console.error('❌ Please provide a valid path to the conversations JSON folder.');
    process.exit(1);
}

const OUTPUT_FILE = path.join(path.dirname(CONVERSATIONS_DIR), 'risk_analysis.csv');

console.log(`🔍 Analyzing risks in: ${CONVERSATIONS_DIR}`);

// Regex Patterns for Secrets
const RISK_PATTERNS = [
    { type: 'AWS Access Key', regex: /AKIA[0-9A-Z]{16}/g },
    // Improved AWS Secret Key regex: 40 chars of base64-like chars, but exclude common false positives like paths or long hex strings
    {
        type: 'AWS Secret Key',
        regex: /(?<![A-Za-z0-9/+=])(?![0-9a-fA-F]{40})(?![0-9]+$)[A-Za-z0-9/+=]{40}(?![A-Za-z0-9/+=])/g,
        contextRequired: ['aws', 'secret', 'key', 'access']
    },
    { type: 'Google API Key', regex: /AIza[0-9A-Za-z\\-_]{35}/g },
    { type: 'OpenAI API Key', regex: /sk-[a-zA-Z0-9]{20,}/g },
    { type: 'Anthropic API Key', regex: /sk-ant-[a-zA-Z0-9]{20,}/g },
    { type: 'Stripe Live Key', regex: /sk_live_[0-9a-zA-Z]{24}/g },
    { type: 'Private Key', regex: /-----BEGIN [A-Z ]+ PRIVATE KEY-----/g },
    { type: 'Generic API Key', regex: /(api_key|apikey|access_token|secret_token)\s*[:=]\s*['"]([a-zA-Z0-9_\-]{16,})['"]/gi, group: 2 },
    { type: 'Password Exposure', regex: /(password|passwd|pwd)\s*[:=]\s*['"]([^'"]{6,})['"]/gi, group: 2 }
];

const files = fs.readdirSync(CONVERSATIONS_DIR).filter(f => f.endsWith('.json'));
const risks = [];

files.forEach((file, idx) => {
    const filePath = path.join(CONVERSATIONS_DIR, file);
    let events;
    try {
        events = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    } catch (err) {
        console.error(`Error parsing ${file}:`, err);
        return;
    }

    events.forEach(e => {
        let contentToCheck = '';
        let role = 'unknown';

        if (e.type === 'user' && e.message?.content) {
            role = 'User';
            contentToCheck = typeof e.message.content === 'string' ? e.message.content : JSON.stringify(e.message.content);
        } else if (e.type === 'assistant' && e.message?.content) {
            role = 'Assistant';
            contentToCheck = typeof e.message.content === 'string' ? e.message.content : JSON.stringify(e.message.content);
        } else if (e.type === 'tool_result' || (e.type === 'user' && Array.isArray(e.message?.content))) {
            // Check tool outputs too
            role = 'Tool Output';
            contentToCheck = JSON.stringify(e);
        }

        if (!contentToCheck) return;

        RISK_PATTERNS.forEach(pattern => {
            let match;
            // Reset regex state
            pattern.regex.lastIndex = 0;

            // For global regexes, we loop
            if (pattern.regex.flags.includes('g')) {
                while ((match = pattern.regex.exec(contentToCheck)) !== null) {
                    validateAndAddRisk(match, pattern, file, e.timestamp, role, contentToCheck);
                }
            } else {
                match = pattern.regex.exec(contentToCheck);
                if (match) {
                    validateAndAddRisk(match, pattern, file, e.timestamp, role, contentToCheck);
                }
            }
        });
    });

    if ((idx + 1) % 50 === 0) process.stdout.write('.');
});

function validateAndAddRisk(match, pattern, file, timestamp, role, fullContent) {
    const secret = pattern.group ? match[pattern.group] : match[0];

    // Heuristic check for generic secrets (avoid false positives like "password" in text)
    if (pattern.contextRequired) {
        const lowerContent = fullContent.toLowerCase();
        const hasContext = pattern.contextRequired.some(word => lowerContent.includes(word));
        if (!hasContext) return;
    }

    // FILTER: Ignore common false positives
    // 1. File paths (e.g., file:///Users/...)
    if (fullContent.includes(`file://${secret}`) || fullContent.includes(`/${secret}`)) return;
    // 2. URLs (e.g., https://...)
    if (fullContent.includes(`http://${secret}`) || fullContent.includes(`https://${secret}`)) return;
    // 3. Node modules paths
    if (fullContent.includes('node_modules') && fullContent.includes(secret)) return;
    // 4. Git commit hashes (usually hex) - if the secret is purely hex, ignore it (unless it's a specific key type known to be hex)
    const isHex = /^[0-9a-fA-F]+$/.test(secret);
    if (isHex && pattern.type === 'AWS Secret Key') return; // AWS secret keys are NOT just hex

    // Redact secret for report
    const redacted = secret.substring(0, 4) + '...' + secret.substring(secret.length - 4);

    // Get context (surrounding text)
    const start = Math.max(0, match.index - 50);
    const end = Math.min(fullContent.length, match.index + secret.length + 50);
    const context = fullContent.substring(start, end).replace(/\n/g, ' ').replace(secret, redacted);

    risks.push({
        File: file,
        Timestamp: timestamp || 'N/A',
        Role: role,
        Risk_Type: pattern.type,
        Snippet: redacted,
        Full_Secret: secret,
        Context: context
    });
}

console.log('\n');

// Output Results
if (risks.length === 0) {
    console.log('✅ No risks found!');
} else {
    console.log(`⚠️  Found ${risks.length} potential risks.`);

    // CSV Header
    const csvHeader = 'File,Timestamp,Role,Risk_Type,Snippet,Full_Secret,Context\n';

    const csvRows = risks.map(r => {
        const cleanContext = `"${(r.Context || '').replace(/"/g, '""')}"`;
        return `${r.File},${r.Timestamp},${r.Role},${r.Risk_Type},${r.Snippet},${r.Full_Secret},${cleanContext}`;
    }).join('\n');

    fs.writeFileSync(OUTPUT_FILE, csvHeader + csvRows);
    console.log(`✅ Risk report saved to: ${OUTPUT_FILE}`);
}
