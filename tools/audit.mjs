// Opens every screen of the book in headless Chrome and reports problems.
//   node tools/audit.mjs [outDir] [baseUrl]
// Needs the book served over http (e.g. `python3 -m http.server 8765` in the repo root).
// Writes outDir/report.json and one desktop screenshot per screen.
import { spawn } from 'node:child_process';
import { setTimeout as sleep } from 'node:timers/promises';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const out = path.resolve(process.argv[2] || '/tmp/book-audit');
const BASE = process.argv[3] || 'http://127.0.0.1:8765/';
fs.mkdirSync(out, { recursive: true });
const pages = JSON.parse(fs.readFileSync(path.join(root, 'content/pages.json'), 'utf8'));
const only = process.env.ONLY ? new RegExp(process.env.ONLY) : null;

const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', [
  '--headless=new', '--disable-gpu', '--no-first-run', '--hide-scrollbars', '--remote-debugging-port=9334',
  `--user-data-dir=${out}/profile`, '--window-size=1280,1000', 'about:blank'], { stdio: 'ignore' });

let ws, id = 0;
const pending = new Map();
let errors = [];
for (let i = 0; i < 60 && !ws; i++) {
  try {
    const tabs = await (await fetch('http://127.0.0.1:9334/json')).json();
    const tab = tabs.find(t => t.type === 'page');
    if (tab) ws = new WebSocket(tab.webSocketDebuggerUrl);
  } catch { await sleep(250); }
}
await new Promise(r => ws.addEventListener('open', r));
ws.addEventListener('message', e => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m.result || m.error); pending.delete(m.id); }
  if (m.method === 'Runtime.exceptionThrown') errors.push(m.params.exceptionDetails.exception?.description?.slice(0, 300) || m.params.exceptionDetails.text);
  if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') errors.push('console.error: ' + m.params.args.map(a => a.value || a.description).join(' ').slice(0, 300));
  if (m.method === 'Network.loadingFailed' && !m.params.canceled) errors.push('network: ' + m.params.errorText);
  // two optional files the reader probes for and does not need
  if (m.method === 'Network.responseReceived' && m.params.response.status >= 400 && !/(audio|timecode)_voices\.json/.test(m.params.response.url)) errors.push(`http ${m.params.response.status}: ${m.params.response.url.replace(BASE, '')}`);
});
const send = (method, params = {}) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async (expression) => (await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })).result?.value;
const size = (w, h) => send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: 1, mobile: w < 600 });

const CHECK = `(() => {
  const c = document.getElementById('content');
  const issues = [];
  const name = el => (el.getAttribute('aria-label') || (el.getAttribute('aria-labelledby') || '').split(' ').map(i => document.getElementById(i)?.textContent || '').join(' ') || (el.id && document.querySelector('label[for="' + el.id + '"]')?.textContent) || el.closest('label')?.textContent || el.textContent || el.getAttribute('title') || '').trim();
  c.querySelectorAll('img').forEach(i => {
    if (i.complete && !i.naturalWidth) issues.push('broken image ' + i.getAttribute('src'));
    if (!i.hasAttribute('alt')) issues.push('img without alt ' + i.getAttribute('src'));
    else if (!i.getAttribute('alt').trim() && !i.closest('[aria-hidden="true"]')) issues.push('img with empty alt outside decoration ' + i.getAttribute('src'));
  });
  c.querySelectorAll('input:not([type=hidden]), textarea, select, button, a[href], [role=button], [role=option]').forEach(el => {
    if (el.closest('[hidden]')) return;
    if (!name(el)) issues.push('no accessible name: ' + el.tagName.toLowerCase() + (el.id ? '#' + el.id : ''));
    const r = el.getBoundingClientRect();
    if (r.width && (r.height < 44 || r.width < 44) && !el.closest('p, li, td') ) issues.push('small target ' + Math.round(r.width) + 'x' + Math.round(r.height) + ' ' + el.tagName.toLowerCase());
  });
  c.querySelectorAll('label[for]').forEach(l => { if (!document.getElementById(l.getAttribute('for'))) issues.push('label for missing #' + l.getAttribute('for')); });
  const ids = {}; document.querySelectorAll('[id]').forEach(e => ids[e.id] = (ids[e.id] || 0) + 1);
  Object.keys(ids).filter(k => ids[k] > 1).forEach(k => issues.push('duplicate id ' + k));
  const h1 = c.querySelectorAll('h1').length; if (h1 !== 1) issues.push(h1 + ' h1 elements');
  let last = 1; c.querySelectorAll('h1,h2,h3,h4').forEach(h => { const n = +h.tagName[1]; if (n > last + 1) issues.push('heading jumps to ' + h.tagName); last = n; });
  c.querySelectorAll('table').forEach(t => { if (!t.querySelector('th')) issues.push('table without header cells'); });
  if (!document.documentElement.lang) issues.push('no lang');
  c.querySelectorAll('[data-id]').forEach(e => { if (!e.textContent.trim() && e.tagName !== 'IMG') issues.push('empty text ' + e.getAttribute('data-id')); });
  const over = document.documentElement.scrollWidth - document.documentElement.clientWidth;
  if (over > 1) issues.push('horizontal overflow ' + over + 'px');
  c.querySelectorAll('*').forEach(e => { const r = e.getBoundingClientRect(); if (r.width > 4 && (r.right > innerWidth + 1 || r.left < -1) && !e.closest('.lx-table-wrap')) issues.push('element outside viewport: ' + e.tagName.toLowerCase() + '.' + (e.className + '').split(' ')[0]); });
  return JSON.stringify({ issues: [...new Set(issues)], height: Math.ceil(c.getBoundingClientRect().height),
    type: c.querySelector('section')?.getAttribute('data-section-type'), fonts: document.fonts.status,
    submit: !![...document.querySelectorAll('button')].find(b => !b.closest('#content') && /Dërgo/.test(b.textContent)),
    styled: getComputedStyle(c).maxWidth });
})()`;

await send('Runtime.enable'); await send('Page.enable'); await send('Network.enable');
const report = [];
for (const p of pages) {
  if (only && !only.test(p.section_id)) continue;
  errors = [];
  await size(1280, 1000);
  await send('Page.navigate', { url: BASE + p.href });
  await sleep(1500);
  for (let i = 0; i < 20; i++) { if (await ev(`document.readyState === 'complete' && !!document.querySelector('#interface-container *') && [...document.images].every(i => i.complete)`)) break; await sleep(300); }
  await sleep(500);
  const raw = await ev(CHECK);
  if (!raw) { console.log(p.section_id, '| PAGE DID NOT LOAD'); report.push({ id: p.section_id, desktop: ['did not load'], phone: [], errors: [] }); continue; }
  const desktop = JSON.parse(raw);
  const h = Math.min(Math.max(desktop.height + 120, 700), 2200);
  await size(1280, h); await sleep(150);
  const shot = await send('Page.captureScreenshot', { format: 'jpeg', quality: 60 });
  fs.writeFileSync(path.join(out, p.section_id + '.jpg'), Buffer.from(shot.data, 'base64'));
  await size(390, 800); await sleep(500);
  const phone = JSON.parse(await ev(CHECK));
  const entry = { id: p.section_id, type: desktop.type, submit: desktop.submit, height: desktop.height,
    desktop: desktop.issues, phone: phone.issues.filter(i => !desktop.issues.includes(i)), errors: [...new Set(errors)] };
  report.push(entry);
  const all = [...entry.desktop, ...entry.phone.map(i => 'phone: ' + i), ...entry.errors];
  if (all.length) console.log(p.section_id, '|', all.join(' ; '));
}
fs.writeFileSync(path.join(out, 'report.json'), JSON.stringify(report, null, 1));
const bad = report.filter(r => r.desktop.length || r.phone.length || r.errors.length).length;
console.log(`${report.length} screens checked, ${bad} with findings. Activities without Submit: ` +
  report.filter(r => /^activity_/.test(r.type || '') && !r.submit).map(r => r.id).join(' '));
ws.close(); chrome.kill(); process.exit(0);
