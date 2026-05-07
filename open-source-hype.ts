import dotenv from "dotenv";
import fs from "fs";
import path from "path";
import { z } from "zod";
import { Stagehand, type LogLine } from "@browserbasehq/stagehand";

dotenv.config();

const CACHE_DIR = path.resolve("stagehand-cache/open-source-hype");
const OUTPUT_DIR = path.resolve("outputs");
const OUTPUT_FILE = path.join(OUTPUT_DIR, "top-open-source-hype.json");

const MODEL_NAME = process.env.STAGEHAND_MODEL_NAME ?? "google/gemini-3-flash-preview";

if (!process.env.BROWSERBASE_API_KEY) {
    throw new Error("Missing BROWSERBASE_API_KEY");
}

if (MODEL_NAME.startsWith("google/") && !process.env.GOOGLE_API_KEY) {
    throw new Error("Missing GOOGLE_API_KEY for google/... model");
}

fs.mkdirSync(CACHE_DIR, { recursive: true });
fs.mkdirSync(OUTPUT_DIR, { recursive: true });

const ReportSchema = z.object({
    tools: z.array(
        z.object({
            rank: z.number(),
            name: z.string(),
            category: z.string(),
            repoOrHomepage: z.string(),
            shortSummary: z.string(),
            whyTrending: z.string(),
            whatItDoesDifferently: z.string(),
            whoShouldCare: z.string(),
            evidence: z.string(),
        })
    ).length(5),
});

function appLog(message: string, data?: unknown) {
    console.log(`\n[APP] ${message}`);
    if (data !== undefined) {
        console.log(JSON.stringify(data, null, 2));
    }
}

function stagehandLogger(line: LogLine) {
    const level =
        line.level === 0 ? "ERROR" : line.level === 1 ? "INFO" : "DEBUG";

    console.log(`[STAGEHAND ${level}] [${line.category}] ${line.message}`);

    if (line.auxiliary) {
        console.log(`[STAGEHAND AUX] ${JSON.stringify(line.auxiliary, null, 2)}`);
    }
}

function listCacheFiles() {
    if (!fs.existsSync(CACHE_DIR)) return [];

    return fs.readdirSync(CACHE_DIR, { recursive: true }).map(String);
}

async function main() {
    appLog("Starting script");
    appLog("Model", MODEL_NAME);
    appLog("Cache directory", CACHE_DIR);

    const beforeCacheFiles = listCacheFiles();
    appLog("Cache files before run", beforeCacheFiles);

    const stagehand = new Stagehand({
        env: "BROWSERBASE",
        apiKey: process.env.BROWSERBASE_API_KEY,

        // Keep the full provider/model format.
        model: MODEL_NAME,

        // File-based local cache.
        cacheDir: CACHE_DIR,

        serverCache: true,
        selfHeal: true,
        experimental: true,
        verbose: 2,
        logger: stagehandLogger,
    });

    try {
        appLog("Initializing Stagehand");
        await stagehand.init();

        appLog("Browserbase session", {
            sessionId: stagehand.browserbaseSessionID,
            sessionUrl: stagehand.browserbaseSessionURL,
        });

        const page = stagehand.context.pages()[0];

        appLog("Navigating to GitHub Trending");
        await page.goto("https://github.com/trending?since=weekly");

        appLog("Current page", {
            title: await page.title(),
            url: await page.url(),
        });

        /**
         * IMPORTANT:
         * This is the cache-forcing step.
         *
         * Stagehand docs show cacheDir being used with stagehand.act(...).
         * So we intentionally call a simple act instruction here.
         */
        appLog("Running cached Stagehand act step");
        await stagehand.act("scroll down");

        const afterActCacheFiles = listCacheFiles();
        appLog("Cache files after stagehand.act", afterActCacheFiles);

        appLog("Extracting candidates from GitHub Trending");

        const githubResult = await stagehand.extract({
            instruction: `
Extract open-source repositories from the current GitHub Trending page.
Focus on developer tools, AI libraries, coding tools, infrastructure tools,
frameworks, databases, and productivity software.

For each candidate, include:
- repo name
- repo URL if visible
- description
- programming language if visible
- visible evidence such as stars today, rank, or description
      `.trim(),
            schema: z.object({
                candidates: z.array(
                    z.object({
                        name: z.string(),
                        repoUrl: z.string().optional(),
                        description: z.string(),
                        language: z.string().optional(),
                        visibleEvidence: z.string(),
                    })
                ),
            }),
        });

        appLog("GitHub extraction complete", githubResult);

        appLog("Navigating to Hacker News for extra hype signals");
        await page.goto("https://news.ycombinator.com");

        appLog("Running second cached Stagehand act step");
        await stagehand.act("scroll down");

        const afterSecondActCacheFiles = listCacheFiles();
        appLog("Cache files after second stagehand.act", afterSecondActCacheFiles);

        appLog("Extracting Hacker News developer-tool posts");

        const hnResult = await stagehand.extract({
            instruction: `
Extract posts on this Hacker News page related to open-source tools,
developer libraries, AI software, programming frameworks, infrastructure,
databases, browsers, agents, or developer productivity.

For each matching post, include:
- title
- URL if visible
- visible points/comments if visible
- why it is relevant
      `.trim(),
            schema: z.object({
                posts: z.array(
                    z.object({
                        title: z.string(),
                        url: z.string().optional(),
                        visibleEvidence: z.string(),
                        relevance: z.string(),
                    })
                ),
            }),
        });

        appLog("Hacker News extraction complete", hnResult);

        appLog("Synthesizing final top 5 report");

        const report = await stagehand.extract({
            instruction: `
Use this extracted evidence to create a top 5 report.

GitHub Trending evidence:
${JSON.stringify(githubResult, null, 2)}

Hacker News evidence:
${JSON.stringify(hnResult, null, 2)}

Pick exactly 5 currently hyped open-source tools, libraries, or software projects.

For each:
- explain what it is
- explain why it seems hyped
- explain what it does differently from older/common alternatives
- explain who should care
- cite visible evidence from the extracted data

Return exactly 5 tools.
    `.trim(),
            schema: ReportSchema,
        });

        const reportData =
            (report as any).tools
                ? report
                : (report as any).output?.tools
                    ? (report as any).output
                    : (report as any).data?.tools
                        ? (report as any).data
                        : (report as any).extraction?.tools
                            ? (report as any).extraction
                            : null;

        if (!reportData || !Array.isArray((reportData as any).tools)) {
            console.log("\n[DEBUG] Unexpected report shape:");
            console.dir(report, { depth: null });
            throw new Error("Could not find tools array in Stagehand report response.");
        }

        const finalOutput = {
            generatedAt: new Date().toISOString(),
            model: MODEL_NAME,
            cacheDir: CACHE_DIR,
            report: reportData,
        };

        fs.writeFileSync(OUTPUT_FILE, JSON.stringify(finalOutput, null, 2));

        appLog("Saved output", OUTPUT_FILE);

        console.log("\n==============================");
        console.log("Top 5 Open-Source Hype Report");
        console.log("==============================");

        for (const tool of (reportData as any).tools) {
            console.log(`\n${tool.rank}. ${tool.name} — ${tool.category}`);
            console.log(`Repo/Homepage: ${tool.repoOrHomepage}`);
            console.log(`Summary: ${tool.shortSummary}`);
            console.log(`Why trending: ${tool.whyTrending}`);
            console.log(`What different: ${tool.whatItDoesDifferently}`);
            console.log(`Who should care: ${tool.whoShouldCare}`);
            console.log(`Evidence: ${tool.evidence}`);
        }

        const finalCacheFiles = listCacheFiles();
        appLog("Final cache files", finalCacheFiles);

        if (finalCacheFiles.length === 0) {
            console.warn(
                "\n[WARNING] No local cache files were created. This usually means your installed Stagehand package version does not support local cacheDir yet, or the executed methods did not hit the local-cache path."
            );
        }
    } finally {
        appLog("Closing Stagehand");
        await stagehand.close();
    }
}

main().catch((error) => {
    console.error("\n[APP ERROR]");
    console.error(error);
    process.exit(1);
});