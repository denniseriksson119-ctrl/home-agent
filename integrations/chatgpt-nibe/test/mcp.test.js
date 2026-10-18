import { test } from "node:test";
import assert from "node:assert/strict";
import worker, { handle } from "../worker/index.js";

const env = { HOME_AGENT_ORIGIN: "https://pi.example.test", HOME_AGENT_READ_TOKEN: "t".repeat(43) };
const context = {
  contract_version: "0.1", database_schema_version: 5, retrieved_at: "2026-10-18T00:00:00Z",
  context_revision: "a".repeat(64),
  asset: { permanent_id: "synthetic-id", legacy_id: "eq_heat_pump_nibe_s1255", record_yaml: "model: S1255" },
  sources: [], scope: { sources: "explicitly linked sources only" },
};
const request = (method, params, signedIn = true) => new Request("https://site.example.test/mcp", {
  method: "POST", headers: { "Content-Type": "application/json", ...(signedIn ? { "oai-authenticated-user-id": "synthetic-user" } : {}) },
  body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
});
const call = (signedIn = true) => request("tools/call", { name: "home_agent_read_nibe", arguments: {} }, signedIn);
const upstream = () => Promise.resolve(Response.json(context));

test("discovery exposes exactly one read-only tool and no household data", async () => {
  const data = await (await handle(request("tools/list", {}, false), env)).json();
  assert.equal(data.result.tools.length, 1);
  assert.equal(data.result.tools[0].annotations.readOnlyHint, true);
  assert.equal(data.result.tools[0].annotations.destructiveHint, false);
  assert.ok(!JSON.stringify(data).includes(env.HOME_AGENT_READ_TOKEN));
  const init = await (await handle(request("initialize", {}), env)).json();
  assert.equal(init.result.protocolVersion, "2025-03-26");
});

test("anonymous data call is rejected before any Pi access", async () => {
  const response = await handle(call(false), env, () => { throw new Error("must not fetch"); });
  assert.equal(response.status, 401);
});

test("authenticated call forwards fixed path and bearer then returns live context", async () => {
  const response = await handle(call(), env, async (url, options) => {
    assert.equal(String(url), "https://pi.example.test/api/chatgpt/nibe");
    assert.equal(options.headers.Authorization, "Bearer " + env.HOME_AGENT_READ_TOKEN);
    assert.equal(options.method, "GET");
    assert.equal(options.redirect, "manual");
    return upstream();
  });
  const data = await response.json();
  assert.equal(data.result.isError, false);
  assert.deepEqual(JSON.parse(data.result.content[0].text), context);
  assert.equal(response.headers.get("cache-control"), "no-store");
});

test("Worker runtime context is not mistaken for the fetch function", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = upstream;
  try {
    const data = await (await worker.fetch(call(), env, { waitUntil() {} })).json();
    assert.equal(data.result.isError, false);
  } finally { globalThis.fetch = original; }
});

test("tool name and supplied URLs or asset selectors cannot change scope", async () => {
  for (const params of [{ name: "write_asset" }, { name: "home_agent_read_nibe", arguments: { url: "https://other.example" } }]) {
    const data = await (await handle(request("tools/call", params), env, () => { throw new Error("must not fetch"); })).json();
    assert.equal(data.error.code, -32602);
  }
});

test("unconfigured, insecure and invalid origins never fetch", async () => {
  for (const config of [{}, { ...env, HOME_AGENT_ORIGIN: "http://pi.example.test" }, { ...env, HOME_AGENT_ORIGIN: "https://user:secret@pi.example.test/path" }]) {
    let fetched = false;
    const data = await (await handle(call(), config, () => { fetched = true; return upstream(); })).json();
    assert.equal(data.result.isError, true);
    assert.equal(fetched, false);
    assert.ok(!JSON.stringify(data).includes("secret"));
  }
});

test("network errors, redirects, denial and bad bodies give an explicit failure without cached data", async () => {
  const failures = [
    () => { throw new Error("private token and address"); },
    () => Response.redirect("https://other.example.test", 302),
    () => new Response("denied", { status: 401 }),
    () => Response.json({ wrong: "shape" }),
    () => new Response("not-json", { headers: { "Content-Type": "application/json" } }),
    () => new Response("x".repeat(70000), { headers: { "Content-Type": "application/json" } }),
  ];
  for (const failure of failures) {
    const data = await (await handle(call(), env, failure)).json();
    assert.equal(data.result.isError, true);
    assert.ok(!JSON.stringify(data).includes("private token"));
    assert.ok(!JSON.stringify(data).includes("model: S1255"));
  }
});

test("invalid JSON, initialized notification and unsupported HTTP methods", async () => {
  const bad = new Request("https://site.example.test/mcp", { method: "POST", body: "{" });
  assert.equal((await (await handle(bad)).json()).error.code, -32700);
  const notice = new Request("https://site.example.test/mcp", { method: "POST", body: JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" }) });
  assert.equal((await handle(notice)).status, 202);
  assert.equal((await handle(new Request("https://site.example.test/mcp"))).status, 405);
  assert.equal((await handle(new Request("https://site.example.test/other"))).status, 404);
});
