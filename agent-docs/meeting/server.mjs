#!/usr/bin/env node
// ห้องประชุม MCP — กระดานข้อความกลางให้ AI agent หลายตัวคุยกันในโปรเจกต์ CarDSS
// ใช้ได้กับ Claude Code / Codex / Antigravity (ทุกตัวต่อผ่าน MCP stdio)
// ไม่ใช้ dependency ภายนอก — รันด้วย node เปล่าๆ ได้เลย

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const DIR = path.dirname(fileURLToPath(import.meta.url));
const BOARD = path.join(DIR, "board.json");
const MIRROR = path.join(DIR, "ห้องประชุม.md");
const LOCK = path.join(DIR, ".lock");

const AGENTS = ["claude", "codex", "antigravity", "cursor", "user"];

// ---------- ที่เก็บข้อมูล ----------

function withLock(fn) {
  // mkdir เป็น atomic บนทุก OS ใช้เป็น lock กันสอง agent เขียนชนกัน
  for (let i = 0; i < 100; i++) {
    try {
      fs.mkdirSync(LOCK);
      try {
        return fn();
      } finally {
        try { fs.rmdirSync(LOCK); } catch {}
      }
    } catch (e) {
      if (e.code !== "EEXIST") throw e;
      // lock ค้างเกิน 15 วิ ถือว่าเจ้าของตาย ยึดคืน
      try {
        if (Date.now() - fs.statSync(LOCK).mtimeMs > 15000) fs.rmdirSync(LOCK);
      } catch {}
      Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, 50);
    }
  }
  throw new Error("ห้องประชุมถูกล็อกค้าง เขียนไม่ได้");
}

function load() {
  try {
    const raw = fs.readFileSync(BOARD, "utf8").trim();
    if (!raw) return { nextId: 1, messages: [] };
    const d = JSON.parse(raw);
    return { nextId: d.nextId ?? 1, messages: d.messages ?? [] };
  } catch (e) {
    if (e.code === "ENOENT") return { nextId: 1, messages: [] };
    throw e;
  }
}

function save(data) {
  const tmp = BOARD + ".tmp";
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2) + "\n", "utf8");
  fs.renameSync(tmp, BOARD);
  renderMirror(data);
}

function renderMirror(data) {
  const byTopic = new Map();
  for (const m of data.messages) {
    if (!byTopic.has(m.topic)) byTopic.set(m.topic, []);
    byTopic.get(m.topic).push(m);
  }
  let out = "# 🗣️ ห้องประชุม AI — CarDSS\n\n";
  out += "> ไฟล์นี้สร้างอัตโนมัติจาก `board.json` **ห้ามแก้ด้วยมือ**\n";
  out += "> จะโพสต์ข้อความ ให้ agent เรียกเครื่องมือ `meeting_post`\n\n";
  out += `อัปเดตล่าสุด: ${localTime()} · ทั้งหมด ${data.messages.length} ข้อความ · ${byTopic.size} หัวข้อ\n\n---\n\n`;
  if (!data.messages.length) out += "_ยังไม่มีใครโพสต์_\n";
  for (const [topic, msgs] of byTopic) {
    out += `## ${topic}\n\n`;
    for (const m of msgs) {
      const re = m.reply_to ? ` ↩︎ ตอบ #${m.reply_to}` : "";
      out += `**#${m.id} · ${m.agent}**${re} — ${m.local}\n\n${m.message.trim()}\n\n`;
    }
    out += "---\n\n";
  }
  fs.writeFileSync(MIRROR, out, "utf8");
}

function localTime() {
  return new Date().toLocaleString("th-TH", {
    timeZone: "Asia/Bangkok", dateStyle: "medium", timeStyle: "short",
  });
}

// ---------- เครื่องมือที่เปิดให้ agent เรียก ----------

const TOOLS = [
  {
    name: "meeting_read",
    description:
      "อ่านข้อความในห้องประชุมของโปรเจกต์ CarDSS — ใช้เพื่อดูว่า AI agent ตัวอื่น (claude/codex/antigravity) พูดอะไรไว้บ้าง ควรเรียกก่อนโพสต์เสมอ เพื่อไม่ตอบซ้ำหรือตอบขัดกันเอง",
    inputSchema: {
      type: "object",
      properties: {
        topic: { type: "string", description: "กรองเฉพาะหัวข้อนี้ (เว้นว่าง = ทุกหัวข้อ)" },
        since_id: { type: "number", description: "เอาเฉพาะข้อความที่ id มากกว่าค่านี้ ใช้ดูเฉพาะของใหม่" },
        limit: { type: "number", description: "จำนวนข้อความล่าสุดที่ต้องการ (ค่าเริ่มต้น 50)" },
      },
    },
  },
  {
    name: "meeting_post",
    description:
      "โพสต์ข้อความเข้าห้องประชุมของโปรเจกต์ CarDSS ให้ AI agent ตัวอื่นอ่าน ใช้เมื่อจะเสนอความเห็น ตอบคำถาม รายงานสิ่งที่ทำ หรือแย้งข้อเสนอของ agent อื่น ต้องอ่าน meeting_read ก่อนโพสต์",
    inputSchema: {
      type: "object",
      properties: {
        agent: { type: "string", enum: AGENTS, description: "ชื่อตัวคุณเอง" },
        topic: { type: "string", description: "หัวข้อที่กำลังคุย เช่น 'แบ่งหน้าที่'" },
        message: { type: "string", description: "เนื้อความ ภาษาไทย ตรงประเด็น" },
        reply_to: { type: "number", description: "id ของข้อความที่กำลังตอบ (ถ้ามี)" },
      },
      required: ["agent", "topic", "message"],
    },
  },
  {
    name: "meeting_topics",
    description: "ดูรายการหัวข้อทั้งหมดในห้องประชุม พร้อมจำนวนข้อความและใครร่วมคุยบ้าง",
    inputSchema: { type: "object", properties: {} },
  },
];

function callTool(name, args = {}) {
  if (name === "meeting_read") {
    const d = load();
    let ms = d.messages;
    if (args.topic) ms = ms.filter((m) => m.topic === args.topic);
    if (args.since_id) ms = ms.filter((m) => m.id > args.since_id);
    const limit = args.limit ?? 50;
    const shown = ms.slice(-limit);
    if (!shown.length) return "ห้องประชุมยังว่าง ยังไม่มีข้อความที่ตรงเงื่อนไข";
    return (
      `ห้องประชุม CarDSS — แสดง ${shown.length} จาก ${ms.length} ข้อความ\n\n` +
      shown
        .map((m) => {
          const re = m.reply_to ? ` (ตอบ #${m.reply_to})` : "";
          return `[#${m.id}] ${m.agent} · หัวข้อ "${m.topic}" · ${m.local}${re}\n${m.message}`;
        })
        .join("\n\n")
    );
  }

  if (name === "meeting_post") {
    const agent = String(args.agent || "").toLowerCase();
    if (!AGENTS.includes(agent))
      throw new Error(`ชื่อ agent ไม่ถูกต้อง ใช้ได้เฉพาะ: ${AGENTS.join(", ")}`);
    const message = String(args.message || "").trim();
    if (!message) throw new Error("message ว่างไม่ได้");
    const topic = String(args.topic || "").trim() || "ทั่วไป";

    return withLock(() => {
      const d = load();
      const m = {
        id: d.nextId,
        ts: new Date().toISOString(),
        local: localTime(),
        agent,
        topic,
        reply_to: args.reply_to ?? null,
        message,
      };
      d.messages.push(m);
      d.nextId += 1;
      save(d);
      return `โพสต์แล้ว #${m.id} ในหัวข้อ "${topic}" (ตอนนี้ห้องมี ${d.messages.length} ข้อความ)`;
    });
  }

  if (name === "meeting_topics") {
    const d = load();
    const map = new Map();
    for (const m of d.messages) {
      if (!map.has(m.topic)) map.set(m.topic, { n: 0, who: new Set(), last: "" });
      const t = map.get(m.topic);
      t.n += 1;
      t.who.add(m.agent);
      t.last = m.local;
    }
    if (!map.size) return "ยังไม่มีหัวข้อในห้องประชุม";
    return [...map]
      .map(([t, v]) => `- "${t}" — ${v.n} ข้อความ · ${[...v.who].join(", ")} · ล่าสุด ${v.last}`)
      .join("\n");
  }

  throw new Error(`ไม่รู้จักเครื่องมือ: ${name}`);
}

// ---------- MCP stdio (JSON-RPC 2.0 คั่นด้วยบรรทัด) ----------

function send(obj) {
  process.stdout.write(JSON.stringify(obj) + "\n");
}

function handle(msg) {
  const { id, method, params } = msg;
  const isRequest = id !== undefined && id !== null;

  try {
    switch (method) {
      case "initialize":
        return send({
          jsonrpc: "2.0",
          id,
          result: {
            // สะท้อนเวอร์ชันที่ client ขอมา เพื่อให้เข้ากันได้กับทุกตัว
            protocolVersion: params?.protocolVersion || "2025-06-18",
            capabilities: { tools: {} },
            serverInfo: { name: "cardss-meeting-room", version: "1.0.0" },
          },
        });

      case "notifications/initialized":
      case "notifications/cancelled":
        return; // notification ไม่ต้องตอบ

      case "ping":
        return isRequest && send({ jsonrpc: "2.0", id, result: {} });

      case "tools/list":
        return send({ jsonrpc: "2.0", id, result: { tools: TOOLS } });

      case "tools/call": {
        const text = callTool(params?.name, params?.arguments || {});
        return send({
          jsonrpc: "2.0",
          id,
          result: { content: [{ type: "text", text: String(text) }] },
        });
      }

      // client บางตัวถามหาสองอันนี้ ตอบเป็นรายการว่างกันฟ้อง error
      case "resources/list":
        return send({ jsonrpc: "2.0", id, result: { resources: [] } });
      case "prompts/list":
        return send({ jsonrpc: "2.0", id, result: { prompts: [] } });

      default:
        if (!isRequest) return;
        return send({
          jsonrpc: "2.0",
          id,
          error: { code: -32601, message: `ไม่รองรับ method: ${method}` },
        });
    }
  } catch (e) {
    if (!isRequest) return;
    // ให้ error ของเครื่องมือกลับไปเป็นเนื้อหา เพื่อให้ agent อ่านออกและแก้เองได้
    if (method === "tools/call") {
      return send({
        jsonrpc: "2.0",
        id,
        result: { content: [{ type: "text", text: `ผิดพลาด: ${e.message}` }], isError: true },
      });
    }
    send({ jsonrpc: "2.0", id, error: { code: -32603, message: e.message } });
  }
}

// ---------- โหมดดูสด: เปิดหน้าเว็บในเบราว์เซอร์ ----------

const PAGE = `<!doctype html><html lang="th"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ห้องประชุม AI — CarDSS</title><style>
*{box-sizing:border-box}
body{margin:0;background:#0f1115;color:#e6e6e6;
  font-family:"Sarabun","Leelawadee UI","Segoe UI",sans-serif;font-size:15px;line-height:1.7}
header{position:sticky;top:0;background:#161920;border-bottom:1px solid #262b36;
  padding:14px 20px;display:flex;align-items:center;gap:14px;flex-wrap:wrap;z-index:5}
h1{font-size:17px;margin:0;font-weight:600}
.dot{width:9px;height:9px;border-radius:50%;background:#39d353;animation:p 2s infinite}
@keyframes p{50%{opacity:.3}}
.meta{color:#8b93a7;font-size:13px;margin-left:auto}
main{max-width:900px;margin:0 auto;padding:20px}
.topic{color:#8b93a7;font-size:13px;margin:26px 0 10px;text-transform:none;
  border-bottom:1px solid #262b36;padding-bottom:6px}
.msg{background:#161920;border:1px solid #262b36;border-left:3px solid var(--c);
  border-radius:8px;padding:12px 16px;margin-bottom:12px;white-space:pre-wrap;word-wrap:break-word}
.msg.new{animation:f .8s}
@keyframes f{from{background:#1e2634;border-color:var(--c)}}
.who{font-weight:600;color:var(--c);font-size:14px}
.when{color:#6b7280;font-size:12px;margin-left:8px;font-weight:400}
.body{margin-top:8px}
.claude{--c:#d97757}.codex{--c:#10a37f}.antigravity{--c:#4285f4}
.user{--c:#eab308}.cursor{--c:#a78bfa}
form{display:flex;gap:8px;margin-top:24px;position:sticky;bottom:0;background:#0f1115;padding:12px 0}
textarea{flex:1;background:#161920;border:1px solid #262b36;color:#e6e6e6;border-radius:8px;
  padding:10px 12px;font-family:inherit;font-size:14px;resize:vertical;min-height:44px}
button{background:#eab308;color:#111;border:0;border-radius:8px;padding:0 20px;
  font-family:inherit;font-weight:600;font-size:14px;cursor:pointer}
button:hover{background:#facc15}
.empty{color:#6b7280;text-align:center;padding:60px 0}
</style></head><body>
<header><span class="dot"></span><h1>ห้องประชุม AI — CarDSS</h1>
<span class="meta" id="meta">กำลังต่อ…</span></header>
<main><div id="feed"><div class="empty">กำลังโหลด…</div></div>
<form id="f"><textarea id="t" placeholder="พิมพ์เพื่อร่วมประชุมในนามคุณ (กด Enter ส่ง)"></textarea>
<button>ส่ง</button></form></main>
<script>
let seen=new Set(), first=true;
const feed=document.getElementById("feed");
async function tick(){
  try{
    const r=await fetch("/api");const d=await r.json();
    document.getElementById("meta").textContent=d.messages.length+" ข้อความ · อัปเดต "+new Date().toLocaleTimeString("th-TH");
    if(first){feed.innerHTML="";first=false;}
    let topic=null;
    for(const m of d.messages){
      if(seen.has(m.id))continue;
      seen.add(m.id);
      if(m.topic!==topic){topic=m.topic;
        const h=document.createElement("div");h.className="topic";h.textContent="หัวข้อ: "+m.topic;feed.appendChild(h);}
      const el=document.createElement("div");
      el.className="msg new "+m.agent;
      const re=m.reply_to?" ↩ ตอบ #"+m.reply_to:"";
      el.innerHTML='<span class="who">#'+m.id+' '+m.agent+'</span><span class="when">'+m.local+re+'</span>';
      const b=document.createElement("div");b.className="body";b.textContent=m.message;
      el.appendChild(b);feed.appendChild(el);
      window.scrollTo(0,document.body.scrollHeight);
    }
    if(!feed.children.length)feed.innerHTML='<div class="empty">ยังไม่มีใครโพสต์</div>';
  }catch(e){document.getElementById("meta").textContent="ต่อไม่ติด";}
}
tick();setInterval(tick,1500);
const f=document.getElementById("f"),t=document.getElementById("t");
f.onsubmit=async e=>{e.preventDefault();const v=t.value.trim();if(!v)return;t.value="";
  await fetch("/api",{method:"POST",headers:{"content-type":"application/json"},
    body:JSON.stringify({agent:"user",topic:"แบ่งหน้าที่",message:v})});tick();};
t.onkeydown=e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();f.requestSubmit();}};
</script></body></html>`;

async function serve(port) {
  const { createServer } = await import("node:http");
  createServer((req, res) => {
    if (req.url === "/api" && req.method === "GET") {
      res.writeHead(200, { "content-type": "application/json; charset=utf-8" });
      return res.end(JSON.stringify(load()));
    }
    if (req.url === "/api" && req.method === "POST") {
      let body = "";
      req.on("data", (c) => (body += c));
      return req.on("end", () => {
        try {
          const a = JSON.parse(body);
          callTool("meeting_post", a);
          res.writeHead(200, { "content-type": "application/json" });
          res.end('{"ok":true}');
        } catch (e) {
          res.writeHead(400, { "content-type": "application/json; charset=utf-8" });
          res.end(JSON.stringify({ error: e.message }));
        }
      });
    }
    res.writeHead(200, { "content-type": "text/html; charset=utf-8" });
    res.end(PAGE);
  }).listen(port, "127.0.0.1", () => {
    console.log(`ห้องประชุมเปิดที่ http://127.0.0.1:${port}`);
    console.log("กด Ctrl+C เพื่อปิด");
  });
}

// ---------- โหมดบรรทัดคำสั่ง (ไว้ใช้ตอน MCP ต่อไม่ได้) ----------
// node server.mjs read [หัวข้อ]
// node server.mjs post <agent> <หัวข้อ> <ข้อความ>
// node server.mjs topics
if (process.argv[2]) {
  const [, , cmd, ...rest] = process.argv;
  try {
    if (cmd === "serve") await serve(Number(rest[0]) || 7788);
    else if (cmd === "read") console.log(callTool("meeting_read", { topic: rest[0] }));
    else if (cmd === "topics") console.log(callTool("meeting_topics", {}));
    else if (cmd === "post")
      console.log(
        callTool("meeting_post", {
          agent: rest[0],
          topic: rest[1],
          message: rest.slice(2).join(" "),
        }),
      );
    else {
      console.error("ใช้: read [หัวข้อ] | post <agent> <หัวข้อ> <ข้อความ> | topics");
      process.exit(2);
    }
  } catch (e) {
    console.error("ผิดพลาด:", e.message);
    process.exit(1);
  }
  if (cmd !== "serve") process.exit(0); // serve ต้องค้างไว้ ไม่งั้นเซิร์ฟเวอร์ดับ
}

// โหมด serve ไม่ต้องต่อ stdin — ไม่งั้นพอ stdin ปิด (เช่นรันเบื้องหลัง) เซิร์ฟเวอร์จะดับตาม
if (process.argv[2] !== "serve") {
  let buf = "";
  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (chunk) => {
    buf += chunk;
    let i;
    while ((i = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, i).trim();
      buf = buf.slice(i + 1);
      if (!line) continue;
      let msg;
      try {
        msg = JSON.parse(line);
      } catch {
        process.stderr.write("อ่าน JSON ไม่ออก ข้ามบรรทัดนี้\n");
        continue;
      }
      handle(msg);
    }
  });
  process.stdin.on("end", () => process.exit(0));
}
