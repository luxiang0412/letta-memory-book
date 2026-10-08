// Render SVG figures to PNG so you can LOOK at them before inserting into the book.
//   cd scripts/figures && npm i playwright-core   (once; or reuse any node_modules with it)
//   node shot.mjs <svg_dir> <png_out_dir> fig-03-xxx fig-09-yyy ...
// Uses system Chrome; set CHROME=/path/to/chrome to override (e.g. ~/.cache/ms-playwright/chromium-*/chrome-linux/chrome).
import { chromium } from 'playwright-core'

const [dir, out, ...names] = process.argv.slice(2)
if (!dir || !out || !names.length) {
  console.error('usage: node shot.mjs <svg_dir> <png_out_dir> <fig-name>...')
  process.exit(1)
}
const browser = await chromium.launch({ executablePath: process.env.CHROME || '/usr/bin/google-chrome', headless: true })
const page = await browser.newPage()
for (const n of names) {
  await page.goto(`file://${dir}/${n}.svg`)
  const [w, h] = await page.evaluate(() => {
    const s = document.querySelector('svg')
    return [s.viewBox.baseVal.width, s.viewBox.baseVal.height]
  })
  await page.setViewportSize({ width: Math.ceil(w), height: Math.ceil(h) })
  await page.screenshot({ path: `${out}/${n}.png` })
  console.log(`${out}/${n}.png`)
}
await browser.close()
