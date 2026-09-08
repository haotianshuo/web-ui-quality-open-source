#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const net = require("net");
const crypto = require("crypto");

const SENSITIVE = new Set(["authorization", "proxy-authorization", "cookie", "x-api-key", "api-key", "x-auth-token"]);
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
const DANGEROUS_ROUTE_PARTS = new Set(["logout", "log-out", "signout", "sign-out", "delete", "remove", "revoke", "archive", "unsubscribe", "terminate", "reset", "destroy", "buy", "purchase", "confirm", "approve", "promote", "demote", "toggle-admin", "pay", "checkout"]);
const SHA256_HEX = /^[0-9a-f]{64}$/;

function normalizeOrigin(raw) { return new URL(String(raw)).origin; }
function originId(raw) { return crypto.createHash("sha256").update(String(raw)).digest("hex").slice(0, 12); }
function isSensitiveHeader(name) { return SENSITIVE.has(String(name).toLowerCase()); }

// Keep Node Browser approvals byte-for-byte compatible with Python's
// urllib.parse.parse_qsl(..., keep_blank_values=True) + urlencode(...).
// URLSearchParams is intentionally not used: it encodes '~' differently from
// Python's quote_plus and would make a query approval runtime-dependent.
function formEncode(value) {
  const bytes = new TextEncoder().encode(String(value)); let out = "";
  for (const byte of bytes) {
    const unreserved = (byte >= 0x41 && byte <= 0x5a) || (byte >= 0x61 && byte <= 0x7a) || (byte >= 0x30 && byte <= 0x39) || byte === 0x2d || byte === 0x2e || byte === 0x5f || byte === 0x7e;
    if (unreserved) out += String.fromCharCode(byte);
    else if (byte === 0x20) out += "+";
    else out += `%${byte.toString(16).toUpperCase().padStart(2, "0")}`;
  }
  return out;
}

function formDecode(value) {
  const bytes = []; const raw = String(value); let index = 0;
  while (index < raw.length) {
    if (raw[index] === "+") { bytes.push(0x20); index += 1; continue; }
    if (raw[index] === "%" && index + 2 < raw.length && /^[0-9a-fA-F]{2}$/.test(raw.slice(index + 1, index + 3))) {
      bytes.push(parseInt(raw.slice(index + 1, index + 3), 16)); index += 3; continue;
    }
    const codePoint = raw.codePointAt(index); const character = String.fromCodePoint(codePoint);
    for (const byte of new TextEncoder().encode(character)) bytes.push(byte);
    index += character.length;
  }
  return new TextDecoder("utf-8").decode(Uint8Array.from(bytes));
}

function queryDigest(rawQuery) {
  const pairs = [];
  for (const part of String(rawQuery || "").split("&")) {
    if (!part) continue;
    const separator = part.indexOf("=");
    const rawKey = separator < 0 ? part : part.slice(0, separator);
    const rawValue = separator < 0 ? "" : part.slice(separator + 1);
    pairs.push([formDecode(rawKey), formDecode(rawValue)]);
  }
  const canonical = pairs.map(([key, value]) => `${formEncode(key)}=${formEncode(value)}`).join("&");
  return crypto.createHash("sha256").update(canonical, "utf8").digest("hex");
}

function normalizeApprovedRequest(rule) {
  try {
    const rawPath = String((rule && rule.path) || "");
    if (!rawPath.startsWith("/") || rawPath.startsWith("//") || rawPath.includes("*")) return null;
    const parsedPath = new URL(rawPath, "http://wuq.invalid");
    const embeddedQuery = parsedPath.search.startsWith("?") ? parsedPath.search.slice(1) : "";
    const suppliedDigest = String((rule && rule.queryDigest) || "").trim().toLowerCase();
    if (suppliedDigest && !SHA256_HEX.test(suppliedDigest)) return null;
    const embeddedDigest = embeddedQuery ? queryDigest(embeddedQuery) : "";
    if (suppliedDigest && embeddedQuery && suppliedDigest !== embeddedDigest) return null;
    return {
      origin: normalizeOrigin(rule && rule.origin),
      method: String((rule && rule.method) || "").toUpperCase(),
      path: parsedPath.pathname || "/",
      queryDigest: suppliedDigest || embeddedDigest,
    };
  } catch (_) { return null; }
}

function isPrivateLiteral(hostname) {
  const host = String(hostname || "").replace(/^\[|\]$/g, "").toLowerCase();
  if (host === "localhost" || host.endsWith(".localhost")) return true;
  if (net.isIPv4(host)) {
    const p = host.split(".").map(Number);
    return p[0] === 10 || p[0] === 127 || (p[0] === 169 && p[1] === 254) || (p[0] === 172 && p[1] >= 16 && p[1] <= 31) || (p[0] === 192 && p[1] === 168);
  }
  if (net.isIPv6(host)) return host === "::1" || host.startsWith("fc") || host.startsWith("fd") || host.startsWith("fe8") || host.startsWith("fe9") || host.startsWith("fea") || host.startsWith("feb");
  return false;
}

function launchSecurity(config = {}) {
  const args = ["--disable-dev-shm-usage"];
  const degraded = Boolean(config.allowNoSandbox || config.singleProcess);
  if (degraded) {
    if (!config.outerIsolationEvidence) throw new Error("BROWSER_OS_ISOLATION_REQUIRED: unsafe Chromium launch requires explicit outerIsolationEvidence");
    if (config.allowNoSandbox) args.push("--no-sandbox", "--disable-setuid-sandbox", "--no-zygote");
    if (config.singleProcess) args.push("--single-process");
  }
  return {args, degraded, status: degraded ? "PROCESS_LIMITED" : "SANDBOXED"};
}

function networkDecision(rawUrl, method, allowedOrigins, approvedRequests = []) {
  let parsed;
  try { parsed = new URL(String(rawUrl)); } catch (_) { return {allow: false, code: "UNKNOWN_PROTOCOL", url: String(rawUrl)}; }
  if (["data:", "blob:", "about:"].includes(parsed.protocol)) return {allow: true, code: "EMBEDDED_RESOURCE"};
  if (!["http:", "https:"].includes(parsed.protocol)) return {allow: false, code: parsed.protocol === "ws:" || parsed.protocol === "wss:" ? "WEBSOCKET_BLOCKED" : "UNKNOWN_PROTOCOL", url: parsed.href};
  if (!allowedOrigins.has(parsed.origin)) return {allow: false, code: isPrivateLiteral(parsed.hostname) ? "PRIVATE_OR_LOOPBACK_NOT_APPROVED" : "ORIGIN_NOT_APPROVED", origin: parsed.origin, url: parsed.href};
  const verb = String(method || "GET").toUpperCase();
  const rawQuery = parsed.search.startsWith("?") ? parsed.search.slice(1) : "";
  const requestDigest = rawQuery ? queryDigest(rawQuery) : "";
  const routeParts = new Set(parsed.pathname.split("/").filter(Boolean).map(part => part.replaceAll("_", "-").toLowerCase()));
  const dangerousGet = verb === "GET" && [...routeParts].some(part => DANGEROUS_ROUTE_PARTS.has(part));
  const exact = approvedRequests.some(rawRule => {
    const rule = normalizeApprovedRequest(rawRule);
    return Boolean(rule && rule.origin === parsed.origin && rule.method === verb && rule.path === parsed.pathname && rule.queryDigest === requestDigest);
  });
  if (dangerousGet && !exact) return {allow: false, code: "SIDE_EFFECT_ROUTE_BLOCKED", origin: parsed.origin, method: verb, path: parsed.pathname};
  if (SAFE_METHODS.has(verb)) return {allow: true, code: "SAFE_REQUEST", origin: parsed.origin};
  return exact ? {allow: true, code: "EXPLICIT_SIDE_EFFECT_POLICY", origin: parsed.origin} : {allow: false, code: "SIDE_EFFECT_BLOCKED", origin: parsed.origin, method: verb, path: parsed.pathname};
}

function buildCredentialMap(config, allowedOrigins, primaryOrigin) {
  const shared = {...(config.extraHTTPHeaders || {})};
  const safeHeaders = {};
  const sensitive = {};
  for (const [key, value] of Object.entries(shared)) (isSensitiveHeader(key) ? sensitive : safeHeaders)[key] = String(value);
  const explicit = config.credentialHeadersByOrigin || null;
  const credentials = new Map();
  if (Object.keys(sensitive).length) {
    if (new Set([normalizeOrigin(config.beforeUrl), normalizeOrigin(config.afterUrl)]).size > 1 && !explicit) throw new Error("BROWSER_CREDENTIAL_SCOPE_AMBIGUOUS: sensitive headers across multiple primary origins require explicit per-origin mapping");
    credentials.set(primaryOrigin, sensitive);
  }
  if (explicit) {
    for (const [rawOrigin, headers] of Object.entries(explicit)) {
      const o = normalizeOrigin(rawOrigin);
      if (!allowedOrigins.has(o)) throw new Error(`BROWSER_CREDENTIAL_ORIGIN_NOT_ALLOWED: ${o}`);
      const scoped = {};
      for (const [key, value] of Object.entries(headers || {})) {
        if (!isSensitiveHeader(key)) throw new Error(`BROWSER_CREDENTIAL_MAPPING_INVALID: ${key}`);
        scoped[key] = String(value);
      }
      credentials.set(o, scoped);
    }
  }
  return {safeHeaders, credentials};
}

async function createSecureContext(browser, options, policy) {
  const contextOptions = {...options, serviceWorkers: "block", acceptDownloads: false};
  if (Object.keys(policy.safeHeaders || {}).length) contextOptions.extraHTTPHeaders = {...policy.safeHeaders};
  const context = await browser.newContext(contextOptions);
  const audit = {blockedRequests: [], blockedWebSockets: [], credentialsInjected: 0, credentialsStripped: 0};
  await context.route("**/*", async route => {
    const request = route.request();
    const decision = networkDecision(request.url(), request.method(), policy.allowedOrigins, policy.approvedRequests || []);
    if (!decision.allow) { audit.blockedRequests.push({...decision, resourceType: request.resourceType()}); await route.abort("blockedbyclient"); return; }
    const requestOrigin = ["data:", "blob:", "about:"].includes(new URL(request.url()).protocol) ? null : normalizeOrigin(request.url());
    const headers = {...request.headers()};
    for (const key of Object.keys(headers)) {
      if (isSensitiveHeader(key) && (!requestOrigin || !policy.credentials.has(requestOrigin))) { delete headers[key]; audit.credentialsStripped += 1; }
    }
    for (const [key, value] of Object.entries(policy.credentials.get(requestOrigin) || {})) { headers[key] = value; audit.credentialsInjected += 1; }
    await route.continue({headers});
  });
  if (typeof context.routeWebSocket === "function") {
    await context.routeWebSocket("**/*", ws => {
      const raw = ws.url();
      const decision = {allow: false, code: "WEBSOCKET_BLOCKED", url: raw};
      audit.blockedWebSockets.push(decision);
      // A routed WebSocket remains blocked unless connectToServer() is called.
      return;
    });
  }
  context.on("download", async download => { try { await download.cancel(); } catch (_) {} });
  return {context, audit};
}

function locator(page, step) {
  const exact = Boolean(step.exact); let item;
  if (step.selector) item = page.locator(String(step.selector));
  else if (step.role) item = page.getByRole(String(step.role), {name: step.name == null ? undefined : String(step.name), exact});
  else if (step.label) item = page.getByLabel(String(step.label), {exact});
  else if (step.placeholder) item = page.getByPlaceholder(String(step.placeholder), {exact});
  else if (step.testId) item = page.getByTestId(String(step.testId));
  else if (step.text) item = page.getByText(String(step.text), {exact});
  else throw new Error(`Journey step ${step.id || "unknown"} has no locator`);
  return step.nth == null ? item : item.nth(Number(step.nth));
}

async function runJourney(page, steps, outputDir, viewport) {
  const results = []; const journeyDir = path.join(outputDir, "journey", viewport.id); fs.mkdirSync(journeyDir, {recursive: true});
  for (let index = 0; index < steps.length; index += 1) {
    const step = steps[index]; const started = Date.now();
    try {
      const item = ["screenshot", "assert_url"].includes(step.action) ? null : locator(page, step);
      if (step.action === "fill") await item.fill(String(step.value || "")); else if (step.action === "click") await item.click(); else if (step.action === "press") await item.press(String(step.key || "Enter")); else if (step.action === "assert_visible") await item.waitFor({state: "visible"});
      else if (step.action === "assert_text") { const actual = await item.innerText(); const expected = String(step.expected || step.contains || ""); if (!actual.includes(expected)) throw new Error(`expected ${JSON.stringify(expected)} in ${JSON.stringify(actual.slice(0, 180))}`); }
      else if (step.action === "assert_count") { const actual = await item.count(); if (actual !== Number(step.expected)) throw new Error(`expected count ${step.expected}, received ${actual}`); }
      else if (step.action === "assert_url") { if (!page.url().includes(String(step.contains || step.expected || ""))) throw new Error(`unexpected URL ${page.url()}`); }
      else if (step.action === "screenshot") { const filename = String(step.filename || `journey-${index + 1}.png`).replace(/[^a-zA-Z0-9._-]/g, "-"); await page.screenshot({path: path.join(journeyDir, filename), animations: "disabled"}); }
      else throw new Error(`unsupported journey action ${step.action}`);
      results.push({id: step.id || `step-${index + 1}`, action: step.action, viewport, status: "PASS", durationMs: Date.now() - started});
    } catch (error) { results.push({id: step.id || `step-${index + 1}`, action: step.action, viewport, status: "FAIL", durationMs: Date.now() - started, reason: `${error.name}: ${String(error.message).slice(0, 500)}`}); break; }
  }
  return results;
}

const FOCUSABLE_SELECTOR = 'button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[contenteditable="true"],[tabindex]:not([tabindex="-1"])';

async function inspectKeyboard(page) {
  // A focusable-element count is only inventory.  It is not keyboard evidence.
  // Drive the page with real Tab events and require the focused element to be
  // visible and to expose a browser-visible focus indicator.  This keeps a
  // zero-visit/zero-focus report from being promoted to PASS.
  const candidates = await page.locator(FOCUSABLE_SELECTOR).evaluateAll(elements => elements.filter(element => {
    const style = getComputedStyle(element); const rect = element.getBoundingClientRect();
    return !element.disabled && style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity || 1) > 0 && rect.width > 0 && rect.height > 0;
  }).length);
  if (!candidates) return {status: "NOT_APPLICABLE", focusableCount: 0, visitedCount: 0, visibleFocusCount: 0, focusIndicatorCount: 0, attemptedTabs: 0};

  const sampleLimit = Math.min(Math.max(candidates, 1), 16);
  const visited = new Set(); let visibleFocusCount = 0; let focusIndicatorCount = 0; let attemptedTabs = 0;
  await page.evaluate(() => { if (document.activeElement && document.activeElement !== document.body) document.activeElement.blur(); });
  for (let index = 0; index < Math.min(sampleLimit * 2 + 2, 64); index += 1) {
    await page.keyboard.press("Tab"); attemptedTabs += 1;
    const state = await page.evaluate(selector => {
      const element = document.activeElement;
      if (!element || element === document.body || !element.matches(selector)) return {key: null, visible: false, indicator: false};
      const rect = element.getBoundingClientRect(); const style = getComputedStyle(element);
      const visible = style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity || 1) > 0 && rect.width > 0 && rect.height > 0;
      const outline = style.outlineStyle !== "none" && parseFloat(style.outlineWidth || "0") > 0;
      const shadow = style.boxShadow && style.boxShadow !== "none" && !/^rgba?\(0, 0, 0, 0\) 0px 0px 0px 0px$/.test(style.boxShadow);
      const indicator = visible && (outline || shadow || element.matches(":focus-visible"));
      const all = Array.from(document.querySelectorAll(selector));
      return {key: `${element.tagName.toLowerCase()}:${all.indexOf(element)}`, visible, indicator};
    }, FOCUSABLE_SELECTOR);
    if (!state.key || visited.has(state.key)) continue;
    visited.add(state.key); if (state.visible) visibleFocusCount += 1; if (state.indicator) focusIndicatorCount += 1;
    if (visited.size >= sampleLimit && visibleFocusCount >= sampleLimit && focusIndicatorCount >= sampleLimit) break;
  }
  const status = visited.size >= sampleLimit && visibleFocusCount >= sampleLimit && focusIndicatorCount > 0 ? "PASS" : "FAIL";
  return {
    status, focusableCount: candidates, visitedCount: visited.size, visibleFocusCount, focusIndicatorCount,
    sampleLimit, expectedVisitedCount: sampleLimit, attemptedTabs,
    reason: status === "PASS" ? null : "Keyboard Tab traversal did not reach enough visible elements with a visible focus indicator.",
  };
}

async function capture(browser, target, viewport, outputDir, policy) {
  const contextOptions = {viewport: {width: viewport.width, height: viewport.height}, deviceScaleFactor: 1, locale: "en-US", colorScheme: "light", reducedMotion: "reduce"};
  if (viewport.width <= 480) { contextOptions.isMobile = true; contextOptions.hasTouch = true; }
  const {context, audit} = await createSecureContext(browser, contextOptions, policy); const page = await context.newPage();
  const consoleErrors = []; const pageErrors = [];
  page.on("console", message => { if (["error", "warning"].includes(message.type())) consoleErrors.push({type: message.type(), text: message.text().slice(0, 500)}); });
  page.on("pageerror", error => pageErrors.push(String(error).slice(0, 500)));
  let result;
  try {
    const response = await page.goto(target.url, {waitUntil: "domcontentloaded", timeout: 15000}); await page.waitForTimeout(150);
    const metrics = await page.evaluate(() => ({title: document.title || "", innerWidth, innerHeight, bodyScrollWidth: document.body?.scrollWidth || 0, documentScrollWidth: document.documentElement?.scrollWidth || 0, mainPresent: Boolean(document.querySelector("main"))}));
    const screenshotPath = path.join(outputDir, target.label, `${viewport.id}.png`); fs.mkdirSync(path.dirname(screenshotPath), {recursive: true}); await page.screenshot({path: screenshotPath, fullPage: false, animations: "disabled"});
    metrics.keyboard = await inspectKeyboard(page); const horizontalOverflow = Math.max(metrics.bodyScrollWidth, metrics.documentScrollWidth) > metrics.innerWidth + 1; const httpStatus = response ? response.status() : null; const httpOk = httpStatus !== null && httpStatus >= 200 && httpStatus < 300;
    result = {label: target.label, viewport, status: !httpOk || audit.blockedWebSockets.length || metrics.keyboard.status === "FAIL" ? "FAIL" : !horizontalOverflow && consoleErrors.length === 0 && pageErrors.length === 0 ? "PASS" : "PASS_WITH_WARNINGS", httpStatus, screenshotRef: `screenshots/${target.label}/${viewport.id}.png`, metrics, horizontalOverflow, console: consoleErrors, pageErrors, networkPolicy: {blockedRequestCount: audit.blockedRequests.length, blockedWebSocketCount: audit.blockedWebSockets.length, externalOriginsBlocked: Boolean(audit.blockedRequests.length || audit.blockedWebSockets.length), credentials: {injectedHeaderCount: audit.credentialsInjected, strippedHeaderCount: audit.credentialsStripped, valuesRecorded: false}}};
  } catch (error) { result = {label: target.label, viewport, status: "FAIL", reason: `${error.name}: ${String(error.message).slice(0, 500)}`}; } finally { await context.close(); }
  return result;
}

async function main() {
  const configPath = process.argv[2]; if (!configPath) throw new Error("config path is required"); const config = JSON.parse(fs.readFileSync(configPath, "utf8")); const outputDir = path.resolve(config.outputDir); fs.mkdirSync(outputDir, {recursive: true});
  let playwright; try { playwright = require("playwright"); } catch (error) { throw new Error(`PLAYWRIGHT_NODE_UNAVAILABLE: ${error.message}`); }
  const executablePath = config.browserExecutable || playwright.chromium.executablePath(); if (!executablePath || !fs.existsSync(executablePath)) throw new Error(`BROWSER_EXECUTABLE_NOT_FOUND: ${executablePath || "none"}`);
  const security = launchSecurity(config); const browser = await playwright.chromium.launch({headless: true, executablePath, args: security.args}); const browserVersion = browser.version();
  const allowedOrigins = new Set([normalizeOrigin(config.beforeUrl), normalizeOrigin(config.afterUrl), ...(config.allowOrigins || []).map(normalizeOrigin)]); const {safeHeaders, credentials} = buildCredentialMap(config, allowedOrigins, normalizeOrigin(config.afterUrl)); const policy = {allowedOrigins, safeHeaders, credentials, approvedRequests: config.approvedRequests || []};
  const records = []; let journey = [];
  try {
    for (const viewport of config.viewports) { records.push(await capture(browser, {label: "before", url: config.beforeUrl}, viewport, path.join(outputDir, "screenshots"), policy)); records.push(await capture(browser, {label: "after", url: config.afterUrl}, viewport, path.join(outputDir, "screenshots"), policy)); }
    if (Array.isArray(config.journey) && config.journey.length) for (const viewport of config.viewports) { const {context, audit} = await createSecureContext(browser, {viewport: {width: viewport.width, height: viewport.height}, reducedMotion: "reduce"}, policy); const page = await context.newPage(); try { await page.goto(config.afterUrl, {waitUntil: "domcontentloaded", timeout: 15000}); const rows = await runJourney(page, config.journey, outputDir, viewport); if (audit.blockedRequests.length || audit.blockedWebSockets.length) rows.push({id: "network-policy", action: "policy", viewport, status: "FAIL", reason: "Network policy blocked an unsafe journey request"}); journey.push(...rows); } finally { await context.close(); } }
  } finally { await browser.close(); }
  const failures = security.degraded || records.some(item => item.status === "FAIL") || journey.some(item => item.status === "FAIL"); const warnings = [];
  const report = {schemaVersion: "2", producer: "web-ui-quality-node-playwright", status: security.degraded ? "PROCESS_LIMITED" : failures ? "FAIL" : warnings.length ? "PASS_WITH_WARNINGS" : "PASS", browser: "chromium", browserVersion, executablePath, browserSecurity: {sandbox: security.degraded ? "DEGRADED" : "ENABLED", processNetworkIsolation: "NOT_MEASURED", noSandboxAllowed: security.degraded}, beforeUrl: config.beforeUrl, afterUrl: config.afterUrl, conditions: ["secure context factory for capture and journey", "serviceWorkers=block", "acceptDownloads=false", "exact-origin network policy", "credential origins separated from network allowlist"], viewports: config.viewports, records, journey, warnings, claimBoundary: "Browser routing controls are enforced in-process; DNS rebinding resistance and OS/process network isolation are not implied."};
  fs.writeFileSync(path.join(outputDir, "node-browser-report.json"), JSON.stringify(report, null, 2) + "\n"); process.stdout.write(JSON.stringify({status: report.status, report: "node-browser-report.json"})); process.exitCode = failures ? 1 : 0;
}

module.exports = {buildCredentialMap, createSecureContext, isPrivateLiteral, launchSecurity, networkDecision, queryDigest, normalizeApprovedRequest};
if (require.main === module) main().catch(error => { process.stderr.write(`${error.name}: ${error.message}\n`); process.exitCode = 2; });
