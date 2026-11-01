import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const entry = new URL("../web/jongates_bridge.js", import.meta.url);
const editor = new URL("../web/mask-editor.html", import.meta.url);
const extensions = [];
const requests = [];
const listeners = {};
const context = vm.createContext({
  console: { log() {}, warn() {} },
  app: {
    registerExtension(ext) { extensions.push(ext); },
    graphToPrompt: async () => ({ output: { "1": { class_type: "JonGatesBridge" } } }),
  },
  api: { clientId: "frontend-test" },
  window: { location: { origin: "http://localhost" }, addEventListener(type, fn) { listeners[type] = fn; } },
  fetch: async (url, options) => { requests.push({ url, options }); return { ok: true, json: async () => ({ ok: true }) }; },
});
vm.runInContext(fs.readFileSync(entry, "utf8").replace(/^import .*;$/gm, ""), context);
assert.equal(extensions.length, 1);
assert.equal(extensions[0].name, "jongates.maskeditor.entry");

function OtherNode() {}
await extensions[0].beforeRegisterNodeDef(OtherNode, { name: "BlueBoxBridge" }, context.app);
assert.deepEqual(Object.keys(OtherNode.prototype), []);

function Bridge() { this.id = 17; this.widgets = []; }
Bridge.prototype.addWidget = function(type, name, value, callback) { this.widgets.push({ type, name, callback }); };
await extensions[0].beforeRegisterNodeDef(Bridge, { name: "JonGatesBridge" }, context.app);
const bridge = new Bridge();
bridge.onNodeCreated();
assert.equal(bridge.widgets.length, 1);
assert.equal(bridge.widgets[0].name, "继续");
await bridge.widgets[0].callback();
assert.deepEqual(requests.map(r => r.url), ["/jongates/bridge_continue", "/prompt"]);
assert.equal(JSON.parse(requests[0].options.body).node_id, "17");
const menu = [];
bridge.getExtraMenuOptions(null, menu);
assert.ok(menu[0].content.includes("JONGATES"));

// Parse the complete embedded editor program, not just the entry script.
const html = fs.readFileSync(editor, "utf8");
const scripts = [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)];
assert.ok(scripts.length > 0);
for (const [, source] of scripts) new vm.Script(source);
assert.ok(html.includes("JonGatesMaskEditorDB"));
assert.ok(html.includes("jongates_mask_saved"));
console.log("Bridge frontend: independent hook, Continue request, menu and editor syntax PASS");
