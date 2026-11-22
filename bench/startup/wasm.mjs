// Run from the checkout after building the native emitter and runtime.wasm.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, openSync, closeSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { performance } from "node:perf_hooks";
import { fileURLToPath } from "node:url";
import { createCodeMode } from "../../wasm/codemode.mjs";
import { createRunner } from "../../wasm/run.mjs";

const runPython = createCodeMode();
const jsonFilter = readFileSync(new URL("./wasm_json_filter.py", import.meta.url), "utf8");
const tools = new Map([["issues", project => {
  assert.equal(project, "pystachy");
  return "closed\nopen\nopen";
}], ["issue_records", project => {
  assert.equal(project, "pystachy");
  return JSON.stringify([{ state: "closed" }, { state: "open" }, { state: "open" }]);
}]]);

function script(kind, n) {
  if (kind === "hello") return `print("hello", ${n})\n`;
  if (kind === "json-typed") return `${jsonFilter}\nprint("open", count_open_issues(), ${n})\n`;
  if (kind === "json") return `# pystachy: dynamic-any
import json
from typing import Any
from codemode import call

issues: list[dict[str, Any]] = json.loads(call("issue_records", "pystachy"))
opened = 0
for issue in issues:
    if issue["state"] == "open":
        opened += 1
print("open", opened, ${n})
`;
  return `from codemode import call
states = call("issues", "pystachy").split("\\n")
opened = 0
for state in states:
    if state == "open":
        opened += 1
print("open", opened, ${n})
`;
}

function expectOutput(kind, n) {
  return `${kind === "hello" ? "hello" : "open 2"} ${n}\n`;
}

function checkedProcess(command, args, input, expectedStatus = 0) {
  const result = spawnSync(command, args, { input, env: { ...process.env, PYSTACHY_HOME: process.cwd() } });
  if (result.error) throw result.error;
  assert.equal(result.status, expectedStatus, result.stderr?.toString() || String(result.signal));
  return result.stdout;
}

if (process.argv[2] === "--once") {
  process.exitCode = await runPython(script(process.argv[3], Number(process.argv[4])), { tools });
} else {
  const rounds = Number(process.argv[2] ?? 11);
  assert.ok(Number.isSafeInteger(rounds) && rounds > 0);
  const host = createRunner();
  const compiler = "build/wasm/wasm_from_source";
  const directory = mkdtempSync(join(tmpdir(), "pystachy-wasm-bench-"));
  const output = join(directory, "output");
  // Read/validate captured output outside each timed interval.
  async function timedRun(fn, expected) {
    const stdout = openSync(output, "w");
    let duration;
    try {
      const start = performance.now();
      const status = await fn(stdout);
      duration = performance.now() - start;
      assert.equal(status, 0);
    } finally {
      closeSync(stdout);
    }
    assert.equal(readFileSync(output, "utf8"), expected);
    return duration;
  }
  try {
    for (const kind of ["hello", "tools", "json-typed", "json"]) {
      const samples = { compile_ms: [], fresh_guest_ms: [], warm_source_to_exit_ms: [], cold_source_to_exit_ms: [] };
      for (let n = 0; n <= rounds; n++) {
        const expected = expectOutput(kind, n);
        const source = script(kind, n);
        // Distinct source each time. Give each path its own source values so a previously compiled
        // program module cannot satisfy the next path on hosts that cache WebAssembly.compile().
        const start = performance.now();
        const emitted = checkedProcess(compiler, ["-", "-", "-"], source, kind === "json" ? 3 : 0);
        const bytes = kind === "json" ? checkedProcess("wasm/build.sh", ["link"], emitted) : emitted;
        const compiled = performance.now() - start;
        const guest = await timedRun(stdout => host(bytes, { stdout, tools }), expected);
        const next = n + rounds + 1;
        const warm = await timedRun(stdout => runPython(script(kind, next), { stdout, tools }), expectOutput(kind, next));
        const coldStart = performance.now();
        const printed = checkedProcess(process.execPath, ["--disable-warning=ExperimentalWarning",
          fileURLToPath(import.meta.url), "--once", kind, String(n)]);
        const cold = performance.now() - coldStart;
        assert.equal(printed.toString(), expected);
        if (n === 0) continue;
        samples.compile_ms.push(compiled);
        samples.fresh_guest_ms.push(guest);
        samples.warm_source_to_exit_ms.push(warm);
        samples.cold_source_to_exit_ms.push(cold);
      }
      const medians = Object.fromEntries(Object.entries(samples).map(([label, values]) => {
        values.sort((a, b) => a - b);
        const middle = Math.floor(values.length / 2);
        return [label, Number(((values[middle] + values[Math.floor((values.length - 1) / 2)]) / 2).toFixed(2))];
      }));
      console.log(JSON.stringify({ program: kind, backend: kind === "json" ? "llvm" : "direct", samples: rounds, node: process.version, ...medians }));
    }
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
}
