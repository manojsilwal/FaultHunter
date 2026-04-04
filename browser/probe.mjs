import { chromium } from "playwright";

const [, , rawUrl] = process.argv;

if (!rawUrl) {
  console.error("Usage: node browser/probe.mjs <url>");
  process.exit(1);
}

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.goto(rawUrl, { waitUntil: "domcontentloaded", timeout: 120000 });

const title = await page.title();
const bodyText = await page.locator("body").innerText().catch(() => "");
const excerpt = bodyText.replace(/\s+/g, " ").trim().slice(0, 1500);

console.log(JSON.stringify({ url: rawUrl, title, excerpt }, null, 2));
await browser.close();
