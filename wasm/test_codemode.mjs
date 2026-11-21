// Integration tests use the native source frontend, the WASI runtime and the LLVM fallback.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, open, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { createCodeMode } from "./codemode.mjs";
import { createRunner } from "./run.mjs";

const source = 'from codemode import call\nprint(call("lookup", "α"))\n';
const generator = `${source}
def values():
    yield 42
for v in values():
    print(v)
`;

test("source strings and a generator fallback call the host once per run", async t => {
  const dir = await mkdtemp(join(tmpdir(), "pystachy-tools-"));
  t.after(() => rm(dir, { recursive: true, force: true }));
  const path = join(dir, "program.py"), wasm = join(dir, "program.wasm");
  const log = join(dir, "route");
  const options = {};
  let calls = 0;
  options.tools = new Map([["lookup", key => {
    assert.equal(key, "α");
    return `item ${++calls}`;
  }]]);
  const output = join(dir, "out");
  const stream = await open(output, "w");
  t.after(() => stream.close());
  options.stdout = stream.fd;
  const runPython = createCodeMode();
  assert.equal(await runPython(source, options), 0);
  assert.equal(await runPython(source, options), 0);
  await assert.rejects(createCodeMode({ fallback: false })(generator, options), { code: 3 });
  await assert.rejects(runPython("print(unknown_name)\n", options), { code: 1 });
  assert.equal(calls, 2);
  assert.equal(await runPython(generator, options), 0);

  await writeFile(path, generator);
  const build = spawnSync("wasm/build.sh", ["tir", path, wasm], {
    env: { ...process.env, WASM_TIR_LOG: log }, encoding: "utf8",
  });
  assert.equal(build.status, 0, build.stderr);
  assert.match(await readFile(log, "utf8"), / refused: /);
  const compiled = await WebAssembly.compile(await readFile(wasm));
  assert.equal(WebAssembly.Module.customSections(compiled, "pystachy.data").length, 0);
  assert.equal(await createRunner()(compiled, options), 0);
  assert.equal(await readFile(output, "utf8"), "item 1\nitem 2\nitem 3\n42\nitem 4\n42\n");
});
