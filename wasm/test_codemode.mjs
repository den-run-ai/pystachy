// Integration tests use the native source frontend, the WASI runtime and the LLVM fallback.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, open, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { createCodeMode, createCompiler } from "./codemode.mjs";
import { createRunner } from "./run.mjs";

const source = 'from codemode import call\nprint(call("lookup", "α"))\n';
const generatorBody = `
def values():
    yield 42
for v in values():
    print(v)
`;
const generator = source + generatorBody;

test("LLVM fallback catches Python exceptions and lets host errors escape", async t => {
  const script = `from codemode import call

def parse():
    yield int(call("value", "number"))

try:
    for value in parse():
        print(value)
except BaseException as e:
    print("caught", str(e))
`;
  const artifact = await createCompiler()(script);
  assert.equal(artifact.backend, "llvm");
  const run = createRunner();
  const directory = await mkdtemp(join(tmpdir(), "pystachy-command-eh-"));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const out = await open(join(directory, "out"), "w");
  const err = await open(join(directory, "err"), "w");
  t.after(() => Promise.all([out.close(), err.close()]));
  const execute = value => run(artifact.module, {
    tools: new Map([["value", value]]), stdout: out.fd, stderr: err.fd,
  });
  assert.equal(await execute(() => "7"), 0);
  assert.equal(await execute(() => "bad"), 0);
  assert.equal(await execute(() => { throw new Error("tool failed"); }), 134);
  assert.equal(await readFile(join(directory, "out"), "utf8"), "7\ncaught invalid literal for int() with base 10: 'bad'\n");
  assert.match(await readFile(join(directory, "err"), "utf8"), /wasm trap: .*tool failed/);
});

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
  const direct = createCodeMode({ fallback: false });
  const timedOptions = { ...options, executionTimeoutMs: 2000 };
  assert.equal(await direct(source, timedOptions), 0);
  assert.equal(await direct(source, options), 0);
  await assert.rejects(direct(generator, options), { code: 3 });
  await assert.rejects(runPython("print(unknown_name)\n", options), { code: 1 });
  assert.equal(calls, 2);
  assert.equal(await runPython(generator, timedOptions), 0);

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

test("precompiled programs report their route and take fresh state and grants on each run", async t => {
  const compile = createCompiler();
  const run = createRunner();
  const stateful = `import os
from codemode import call
name = "PYSTACHY_WASM_REUSE_TEST"
os.environ[name] = call("lookup", os.getenv(name, "fresh"))
print(os.environ[name])
`;
  const dir = await mkdtemp(join(tmpdir(), "pystachy-compile-"));
  t.after(() => rm(dir, { recursive: true, force: true }));
  const path = join(dir, "out");
  const output = await open(path, "w");
  t.after(() => output.close());
  for (const backend of ["direct", "llvm"]) {
    const artifact = await compile(backend === "direct" ? stateful : stateful + generatorBody);
    assert.ok(artifact.module instanceof WebAssembly.Module);
    assert.equal(artifact.backend, backend);
    if (backend === "llvm") assert.match(artifact.refusal, /^tir_wasm: refused: .*generator/);
    else assert.equal(artifact.refusal, null);
    for (const reply of ["first", "second"]) {
      const tools = new Map([["lookup", previous => {
        assert.equal(previous, "fresh");
        return reply;
      }]]);
      assert.equal(await run(artifact.module, { tools, stdout: output.fd }), 0);
    }
  }
  assert.equal(await readFile(path, "utf8"), "first\nsecond\nfirst\n42\nsecond\n42\n");
  await assert.rejects(compile("print(unknown_name)\n"), { code: 1, message: /unknown_name/ });
  await assert.rejects(createCompiler({ fallback: false })(generator), { code: 3, message: /refused: .*generator/ });
});

test("a deadline applies to a directly compiled Python loop", async () => {
  const run = createCodeMode({ fallback: false });
  const countdown = "i = 1073741824\nwhile i > 0:\n    i -= 1\n";
  await assert.rejects(run(countdown, { executionTimeoutMs: 25 }), { code: "ERR_SCRIPT_EXECUTION_TIMEOUT" });
});

test("direct exception handling matches the CPython recordings", async t => {
  const compile = createCompiler({ fallback: false });
  const run = createRunner();
  const dir = await mkdtemp(join(tmpdir(), "pystachy-exceptions-"));
  t.after(() => rm(dir, { recursive: true, force: true }));
  const cases = [
    "exc_handler_loop_values", "exc_raise", "exc_finally", "exc_recursion_unwind", "exc_uncaught", "exc_exit",
    "exc_class_try", "exc_class_exit", "exc_class_exit_msg",
  ];
  for (const name of cases) {
    await t.test(name, async t => {
      const prefix = `tests/programs/exceptions/${name}`;
      const { module } = await compile(await readFile(`${prefix}.py`, "utf8"));
      const out = join(dir, `${name}.out`), err = join(dir, `${name}.err`);
      const stdout = await open(out, "w"), stderr = await open(err, "w");
      t.after(() => Promise.all([stdout.close(), stderr.close()]));
      const status = await run(module, { stdout: stdout.fd, stderr: stderr.fd });
      assert.equal(await readFile(out, "utf8") + `[exit ${status}]\n`, await readFile(`${prefix}.out`, "utf8"));
      const expectedError = ["exc_uncaught", "exc_class_try", "exc_class_exit_msg"].includes(name) ? await readFile(`${prefix}.err`, "utf8") : "";
      assert.equal(await readFile(err, "utf8"), expectedError);
    });
  }
});

test("Python handlers cannot catch a host tool failure", async t => {
  const dir = await mkdtemp(join(tmpdir(), "pystachy-tool-trap-"));
  t.after(() => rm(dir, { recursive: true, force: true }));
  const err = join(dir, "err");
  const stderr = await open(err, "w");
  t.after(() => stderr.close());
  const program = `from codemode import call
try:
    call("lookup", "")
except BaseException:
    raise SystemExit(77)
`;
  const tools = new Map([["lookup", () => { throw new Error("host tool failed"); }]]);
  const status = await createCodeMode({ fallback: false })(program, { tools, stderr: stderr.fd });
  assert.equal(status, 134);
  assert.equal(await readFile(err, "utf8"), "wasm trap: host tool failed\n");
});
