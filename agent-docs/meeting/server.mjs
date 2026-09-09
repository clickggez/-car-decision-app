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

// ---------- โหมดบรรทัดคำสั่ง (ไว้ใช้ตอน MCP ต่อไม่ได้) ----------
// node server.mjs read [หัวข้อ]
// node server.mjs post <agent> <หัวข้อ> <ข้อความ>
// node server.mjs topics
if (process.argv[2]) {
  const [, , cmd, ...rest] = process.argv;
  try {
    if (cmd === "read") console.log(callTool("meeting_read", { topic: rest[0] }));
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
  process.exit(0);
}

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
