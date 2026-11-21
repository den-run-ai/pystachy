import assert from "node:assert/strict";
import test from "node:test";
import { toolImports } from "./tools.mjs";

test("each call runs once and copies UTF-8 after guest memory growth", () => {
  const memory = new WebAssembly.Memory({ initial: 1 });
  const encoder = new TextEncoder();
  const payload = "\uFEFFcoffee ☕\u0000";
  const input = encoder.encode("echo" + payload);
  new Uint8Array(memory.buffer).set(input);
  let calls = 0;
  const imports = toolImports(new Map([["echo", text => {
    calls++;
    assert.equal(text, payload);
    return text + "!";
  }]]), () => memory);
  const n = imports.call(0, 4, 4, input.length - 4);
  memory.grow(1);
  imports.read(65536, n);
  assert.deepEqual(new Uint8Array(memory.buffer, 65536, n), encoder.encode(payload + "!"));
  assert.equal(calls, 1);
  assert.throws(() => imports.read(0, n), /invalid tool result/);
});

test("the host must grant each tool and return a synchronous Unicode string", () => {
  const memory = new WebAssembly.Memory({ initial: 1 });
  const input = new TextEncoder().encode("constructor");
  new Uint8Array(memory.buffer).set(input);
  const grant = tools => toolImports(tools, () => memory).call(0, input.length, 0, 0);
  assert.throws(() => grant(undefined), /no host tool named constructor/);
  assert.throws(() => grant({ constructor: () => "" }), /must be a Map/);
  for (const invalid of [1, Promise.resolve("answer"), "\uD800"]) {
    assert.throws(() => grant(new Map([["constructor", () => invalid]])), /Unicode string synchronously/);
  }
  assert.equal(grant(new Map([["constructor", () => ""]])), 0);
});
