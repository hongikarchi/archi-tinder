#!/usr/bin/env node
/**
 * ab_screenshot.mjs -- standalone, one-off Playwright script.
 *
 * NOT part of the web-testing/ E2E runner (run.py / runner/). Ad-hoc tool for
 * capturing full-page screenshots of the 4 seeded LLM A/B persona-report
 * boards (Gemini vs GPT x Brutalist vs Minimal). Safe to delete after use.
 *
 * Usage (from web-testing/, after `npm install playwright` there or with a
 * PLAYWRIGHT_BROWSERS_PATH pointed at an existing install):
 *   node ab_screenshot.mjs
 *
 * Requires: FRONTEND_URL (default http://localhost:5174) and BACKEND_URL
 * (default http://localhost:8001) dev servers already running, and
 * backend/.env containing DEV_LOGIN_SECRET.
 */

import { chromium } from 'playwright'
import { readFileSync, mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.resolve(__dirname, '..')

const FRONTEND_URL = process.env.FRONTEND_URL || 'http://localhost:5174'
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8001'
const OUT_DIR = path.join(REPO_ROOT, 'llm-ab-screens')

const BOARDS = [
  { name: '[GEMINI] Brutalist Persona', id: 'f8d47370-3e62-44a4-9aef-7bff5ae71bfa', file: 'gemini-brutalist.png' },
  { name: '[GEMINI] Minimal Persona', id: '1f2bc245-15db-4308-aba9-25da33c800a0', file: 'gemini-minimal.png' },
  { name: '[GPT] Brutalist Persona', id: '5564efca-a196-4b1e-947f-21c2c05ed683', file: 'gpt-brutalist.png' },
  { name: '[GPT] Minimal Persona', id: '61a8d611-2bc8-4d3b-b83e-3bf473ee2a99', file: 'gpt-minimal.png' },
]

// Extra "detail page" bonus shots: one gemini + one gpt board.
const DETAIL_BOARDS = [
  { name: '[GEMINI] Brutalist Persona', id: 'f8d47370-3e62-44a4-9aef-7bff5ae71bfa', file: 'gemini-brutalist-detail.png' },
  { name: '[GPT] Brutalist Persona', id: '5564efca-a196-4b1e-947f-21c2c05ed683', file: 'gpt-brutalist-detail.png' },
]

function readDevLoginSecret() {
  const envPath = path.join(REPO_ROOT, 'backend', '.env')
  const text = readFileSync(envPath, 'utf8')
  const m = text.match(/^DEV_LOGIN_SECRET=(.+)$/m)
  if (!m) throw new Error('DEV_LOGIN_SECRET not found in backend/.env')
  return m[1].trim()
}

async function devLogin() {
  const secret = readDevLoginSecret()
  const res = await fetch(`${BACKEND_URL}/api/v1/auth/dev-login/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ secret }),
  })
  if (!res.ok) {
    throw new Error(`dev-login failed: HTTP ${res.status} ${await res.text()}`)
  }
  const data = await res.json()
  // ProtectedRoute (frontend/src/components/ProtectedRoute.jsx) gates on the
  // App.jsx `userId` React state, seeded from sessionStorage key
  // 'archithon_user' (App.jsx handleLogin: sessionStorage.setItem
  // ('archithon_user', id) where id = user.user_id). The localStorage JWT
  // keys alone are NOT sufficient -- without this, /board/:id/report
  // silently redirects to /login. Discovered empirically via ab_screenshot.py.
  return { access: data.access, refresh: data.refresh, userId: String(data.user.user_id) }
}

async function waitForReport(page) {
  // Success condition: a data: URI report image OR a persona-type heading
  // containing "The " (per app convention, e.g. "The Brutalist Wanderer").
  const successSelector = [
    'img[src^="data:"]',
    'h1:has-text("The ")',
    'h2:has-text("The ")',
  ].join(', ')

  try {
    await page.waitForSelector(successSelector, { timeout: 15000 })
    return { ok: true }
  } catch {
    // Fallback: settle on networkidle + a short pause, then re-check once.
    try {
      await page.waitForLoadState('networkidle', { timeout: 8000 })
    } catch {
      // ignore -- proceed to settle wait regardless
    }
    await page.waitForTimeout(2500)
    const found = await page.$(successSelector)
    if (found) return { ok: true }

    // Detect the "generate" empty-state explicitly, for a clearer failure reason.
    const generateBtn = await page.$('button:has-text("생성"), button:has-text("Generate"), button:has-text("생성하기")')
    if (generateBtn) {
      return { ok: false, reason: 'generate empty-state (no pre-generated report) -- screenshotting anyway' }
    }
    return { ok: false, reason: 'no report image/heading found after networkidle+settle -- screenshotting anyway' }
  }
}

async function main() {
  mkdirSync(OUT_DIR, { recursive: true })

  console.log('[ab_screenshot] dev-login...')
  const { access, refresh, userId } = await devLogin()
  console.log(`[ab_screenshot] tokens acquired (not printed), user_id=${userId}`)

  const browser = await chromium.launch({ headless: true })
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  const page = await context.newPage()

  // Must be on the origin before localStorage/sessionStorage can be set for it.
  await page.goto(FRONTEND_URL, { waitUntil: 'domcontentloaded' })
  await page.evaluate(({ access, refresh, userId }) => {
    localStorage.setItem('archithon_access', access)
    localStorage.setItem('archithon_refresh', refresh)
    sessionStorage.setItem('archithon_user', userId)
  }, { access, refresh, userId })

  const results = []

  for (const board of BOARDS) {
    const url = `${FRONTEND_URL}/board/${board.id}/report`
    console.log(`[ab_screenshot] -> ${board.name} : ${url}`)
    await page.goto(url, { waitUntil: 'domcontentloaded' })
    const status = await waitForReport(page)
    const outPath = path.join(OUT_DIR, board.file)
    await page.screenshot({ path: outPath, fullPage: true })
    results.push({ ...board, url, outPath, ...status })
    console.log(`[ab_screenshot]    screenshot saved: ${outPath} (ok=${status.ok !== false})`)
  }

  const detailResults = []
  for (const board of DETAIL_BOARDS) {
    const url = `${FRONTEND_URL}/board/${board.id}`
    console.log(`[ab_screenshot] (bonus) -> ${board.name} detail : ${url}`)
    try {
      await page.goto(url, { waitUntil: 'domcontentloaded' })
      await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {})
      await page.waitForTimeout(1000)
      const outPath = path.join(OUT_DIR, board.file)
      await page.screenshot({ path: outPath, fullPage: true })
      detailResults.push({ ...board, url, outPath, ok: true })
      console.log(`[ab_screenshot]    bonus screenshot saved: ${outPath}`)
    } catch (e) {
      detailResults.push({ ...board, url, ok: false, reason: String(e) })
      console.log(`[ab_screenshot]    bonus skipped: ${e}`)
    }
  }

  await browser.close()

  console.log('\n=== SUMMARY ===')
  for (const r of results) {
    console.log(`${r.file}: ${r.ok === false ? 'FLAGGED (' + r.reason + ')' : 'OK'}`)
  }
  for (const r of detailResults) {
    console.log(`${r.file}: ${r.ok === false ? 'SKIPPED (' + r.reason + ')' : 'OK (bonus)'}`)
  }
}

main().catch((err) => {
  console.error('[ab_screenshot] FATAL:', err)
  process.exit(1)
})
