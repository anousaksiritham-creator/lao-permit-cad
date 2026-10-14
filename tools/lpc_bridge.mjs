// lpc_bridge.mjs - drive SketchUp extraction through the HTML MCP v2 bridge (port 32124).
//   node lpc_bridge.mjs info
//   node lpc_bridge.mjs extract '{"cuts":[1500],"skip":["17 "]}'   -> starts job, waits for status.json
// Node is not on PATH: C:\Users\This notebook\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const ROOT = 'D:/ANS/Claude/SketchUp-HTML-MCP-v2/SketchUp-HTML-MCP-v2';
const OUT = 'D:/ANS/Claude/CAD train AI/lao-permit-cad/out';
const {bridge} = await import(pathToFileURL(path.join(ROOT, 'server.mjs')).href);
const config = JSON.parse(fs.readFileSync(path.join(ROOT, 'connection.json'), 'utf8'));
const [cmd = 'info', json = '{}'] = process.argv.slice(2);
const sleep = ms => new Promise(r => setTimeout(r, ms));

const info = await bridge(config, 'get_model_info', {});
if (cmd === 'info') { console.log(JSON.stringify(info)); process.exit(0); }

if (cmd === 'extract') {
  const base = path.basename(info.path || 'untitled', '.skp') || 'untitled';
  const statusFile = path.join(OUT, base, 'status.json');
  const args = {...JSON.parse(json), model_session: info.model_session};
  const r = await bridge(config, 'lpc_extract', args);
  console.log('started', JSON.stringify(r));
  const t0 = Date.now();
  let last = '';
  while (Date.now() - t0 < 30 * 60 * 1000) {
    await sleep(3000);
    let st;
    try { st = JSON.parse(fs.readFileSync(statusFile, 'utf8')); } catch { continue; }
    if (st.job !== r.job) continue;
    const line = `${st.state} ${st.step} ${st.t}s`;
    if (line !== last) { console.log(line); last = line; }
    if (st.state === 'done') { console.log(JSON.stringify(st)); process.exit(0); }
    if (st.state === 'error') { console.error(JSON.stringify(st)); process.exit(1); }
  }
  console.error('timeout waiting for extraction'); process.exit(2);
}
console.error('unknown command'); process.exit(1);
