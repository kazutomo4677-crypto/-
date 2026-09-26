// Frame-accurate capture of index.html → numbered JPEGs.
//   node render.mjs <outDir> [fps=30] [subframes=1] [times=comma list]
// Serve this folder over http first (python3 -m http.server 8777).
// With subframes > 1, each output frame is captured at several evenly spaced
// instants inside the shutter so ffmpeg can blend them into motion blur.
import { chromium } from "playwright";
import fs from "node:fs";

const [outDir = "frames", fpsArg = "30", subArg = "1", timesArg] = process.argv.slice(2);
const fps = +fpsArg, sub = +subArg;
fs.mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
page.on("pageerror", (e) => console.error("pageerror", e.message));
await page.goto(`http://localhost:8777/${process.env.PAGE || "index.html"}?capture`);
await page.evaluate(async () => {
  await document.fonts.ready;
  await Promise.all([...document.images].map((i) => i.decode()));
});

const duration = await page.evaluate(() => window.DURATION || 30);
const times = timesArg
  ? timesArg.split(",").map(Number)
  : Array.from({ length: Math.round(duration * fps) * sub }, (_, i) => i / (fps * sub));

let n = 0;
for (const t of times) {
  await page.evaluate((tt) => window.render(tt), t);
  await page.screenshot({ path: `${outDir}/f${String(n++).padStart(5, "0")}.jpg`, type: "jpeg", quality: 94 });
  if (n % 60 === 0) console.log(`${n}/${times.length}`);
}
await browser.close();
