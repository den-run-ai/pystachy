// Small core-Wasm modules make the runner contracts testable without a WASI SDK.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, open, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";
import { createRunner } from "./run.mjs";

const i32 = 0x7f;
const bytes = (items) => {
  assert.ok(items.length < 128); // these fixtures only need single-byte lengths
  return [items.length, ...items];
};
const name = (s) => bytes(Buffer.from(s));
const section = (id, ...contents) => [id, ...bytes(contents.flat())];
const wasm = (...sections) => Uint8Array.from([0, 97, 115, 109, 1, 0, 0, 0, ...sections.flat()]);
const fn = (params, results) => [0x60, ...bytes(params), ...bytes(results)];
const body = (...instructions) => bytes([0, ...instructions, 0x0b]); // no locals, end
const imp = (mod, field, kind, ...desc) => [...name(mod), ...name(field), kind, ...desc];
const exp = (field, kind, index) => [...name(field), kind, index];

// Emulate reactor.c: call program.init and return memory[0] + the relocated pointer at 16.
// The program increments memory[0], which also detects reuse of mutable runtime state.
function reactor(mallocResult = 16) {
  return wasm(
    section(1, 4, fn([], []), fn([i32], [i32]), fn([], [i32]), fn([i32], [])),
    section(2, 2, imp("program", "init", 0, 0), imp("wasi_snapshot_preview1", "proc_exit", 0, 3)),
    section(3, 2, 1, 2),
    section(5, 1, 0, 1),
    section(7, 4, exp("memory", 2, 0), exp("exit", 0, 1), exp("malloc", 0, 2), exp("pys_wasi_run", 0, 3)),
    section(10, 2, body(0x41, mallocResult),
      body(0x10, 0, 0x41, 0, 0x28, 2, 0, 0x41, 16, 0x28, 2, 0, 0x6a)),
  );
}

function program(exitCode) {
  const init = exitCode === undefined
    ? body(0x41, 0, 0x41, 0, 0x28, 2, 0, 0x41, 1, 0x6a, 0x36, 2, 0)
    : body(0x41, exitCode, 0x10, 0);
  return wasm(
    section(0, name("pystachy.data"), 4),
    section(0, name("pystachy.reloc"), 1, 0),
    section(1, 2, fn([], []), fn([i32], [])),
    section(2, 2, imp("env", "memory", 2, 0, 1), imp("rt", "exit", 0, 1)),
    section(3, 1, 0),
    section(7, 1, exp("init", 0, 1)),
    section(10, 1, init),
  );
}

// Exit with the errno from fd_close(1) or fd_renumber(1, 2).
function closeStdout(move) {
  const close = move ? [0x41, 1, 0x41, 2, 0x10, 0] : [0x41, 1, 0x10, 0];
  return wasm(
    section(1, 3, fn(move ? [i32, i32] : [i32], [i32]), fn([i32], []), fn([], [])),
    section(2, 2, imp("wasi_snapshot_preview1", move ? "fd_renumber" : "fd_close", 0, 0),
      imp("wasi_snapshot_preview1", "proc_exit", 0, 1)),
    section(3, 1, 2), section(5, 1, 0, 1),
    section(7, 2, exp("memory", 2, 0), exp("_start", 0, 2)),
    section(10, 1, body(...close, 0x10, 1)),
  );
}

// Exit with the number of WASI arguments (or environment entries); optionally trap instead.
function command(getSizes = "args_sizes_get", trap = false) {
  return wasm(
    section(1, 3, fn([i32, i32], [i32]), fn([i32], []), fn([], [])),
    section(2, 2, imp("wasi_snapshot_preview1", getSizes, 0, 0),
      imp("wasi_snapshot_preview1", "proc_exit", 0, 1)),
    section(3, 1, 2),
    section(5, 1, 0, 1),
    section(7, 2, exp("memory", 2, 0), exp("_start", 0, 2)),
    section(10, 1, trap ? body(0x00) : body(0x41, 0, 0x41, 4, 0x10, 0, 0x1a, 0x41, 0, 0x28, 2, 0, 0x10, 1)),
  );
}

// Exit with f(1,000,000) & 255 = 64, where f(n) = n ? f(n - 1) + 1 : 0 holds a million frames:
// tens of MiB, past V8's default stack of under 1 MiB.
function recurse() {
  const f = [0x20, 0, 0x04, i32, 0x20, 0, 0x41, 1, 0x6b, 0x10, 1, 0x41, 1, 0x6a, 0x05, 0x41, 0, 0x0b];
  return wasm(
    section(1, 3, fn([i32], [i32]), fn([i32], []), fn([], [])),
    section(2, 1, imp("wasi_snapshot_preview1", "proc_exit", 0, 1)),
    section(3, 2, 0, 2),
    section(5, 1, 0, 1),
    section(7, 2, exp("memory", 2, 0), exp("_start", 0, 2)),
    section(10, 2, body(...f), body(0x41, 0xc0, 0x84, 0x3d, 0x10, 1, 0x41, 0xff, 0x01, 0x71, 0x10, 0)),
  );
}

// Do finite CPU work in the normal entry point, or in the Wasm start section
// that runs before the instance constructor returns. Both routes use the same loop.
function countdown(entry, runAtInstantiation) {
  const loop = [
    1, 1, i32,                                     // one i32 counter local
    0x41, 1, 0x41, 30, 0x74, 0x21, 0,              // counter = 1 << 30
    0x03, 0x40,                                    // loop
    0x20, 0, 0x41, 1, 0x6b, 0x22, 0, 0x0d, 0,      // repeat while --counter
    0x0b, 0x0b,                                    // end loop and function
  ];
  return wasm(
    ...(entry === "init" ? [section(0, name("pystachy.data"), 0)] : []),
    section(1, 1, fn([], [])), section(3, 2, 0, 0), section(5, 1, 0, 1),
    section(7, 2, exp("memory", 2, 0), exp(entry, 0, runAtInstantiation ? 1 : 0)),
    ...(runAtInstantiation ? [section(8, 0)] : []),
    section(10, 2, bytes(loop), body()),
  );
}

async function temp(t) {
  const dir = await mkdtemp(join(tmpdir(), "pystachy-runner-"));
  t.after(() => rm(dir, { recursive: true, force: true }));
  return dir;
}

test("one runtime load, fresh instances for concurrent and subsequent calls", async (t) => {
  const path = join(await temp(t), "runtime.wasm");
  const run = createRunner(path);
  const compiled = await WebAssembly.compile(program());
  await assert.rejects(run(compiled), { code: "ENOENT" });
  await writeFile(path, reactor());
  assert.deepEqual(await Promise.all([run(compiled), run(compiled)]), [17, 17]);
  await rm(path);
  assert.equal(await run(program(23)), 23); // proc_exit returns to the host
  assert.equal(await run(compiled), 17);
});

test("an exception-enabled program rejects an older reactor", async () => {
  const guest = Uint8Array.from([...program(), ...section(0, name("pystachy.eh"))]);
  await assert.rejects(createRunner(reactor())(guest), /requires a runtime with catchable exceptions/);
});

test("standalone commands receive per-run args and environment", async () => {
  const run = createRunner("unused-runtime.wasm");
  assert.equal(await run(command(), { args: ["test", "a", "b"] }), 3);
  assert.equal(await run(command("environ_sizes_get"), { env: { KEY: "value" } }), 1);
  assert.equal(await run(command("environ_sizes_get")), 0);
});

test("execution deadlines interrupt command and reactor guests and leave the runner reusable", async () => {
  const run = createRunner(reactor());
  for (const entry of ["_start", "init"]) {
    for (const runAtInstantiation of [false, true]) {
      const guest = await WebAssembly.compile(countdown(entry, runAtInstantiation));
      await assert.rejects(run(guest, { executionTimeoutMs: 25 }), { code: "ERR_SCRIPT_EXECUTION_TIMEOUT" });
    }
  }
  assert.equal(await run(command(), { executionTimeoutMs: 2000 }), 1);
  assert.equal(await run(program(), { executionTimeoutMs: 2000 }), 17);
  assert.equal(await run(program()), 17);
  await assert.rejects(run(command(), { executionTimeoutMs: 0 }), { code: "ERR_OUT_OF_RANGE" });
});

test("embedded runs cannot close or renumber borrowed stdio or mount directories", async (t) => {
  const handle = await open(join(await temp(t), "stdout"), "w");
  try {
    const run = createRunner();
    const options = { stdout: handle.fd, stderr: handle.fd };
    for (const move of [false, true]) {
      assert.equal(await run(closeStdout(move), options), 58); // ENOTSUP
      await handle.write("still open");
    }
    await assert.rejects(run(command(), { preopens: { "/": "/" } }), /directory mounts/);
  } finally {
    await handle.close();
  }
});

test("allocation failure and command traps return to the caller", async (t) => {
  const path = join(await temp(t), "err");
  const fd = await open(path, "w");
  try {
    const run = createRunner(reactor(0));
    assert.equal(await run(program(), { stderr: fd.fd }), 1);
    assert.equal(await run(command("args_sizes_get", true), { stderr: fd.fd }), 134);
  } finally {
    await fd.close();
  }
  assert.match(await readFile(path, "utf8"), /MemoryError:.*\nwasm trap: unreachable/);
});

test("CLI preserves argv and guest exit status", async (t) => {
  const path = join(await temp(t), "command.wasm");
  await writeFile(path, command());
  const cli = spawnSync(process.execPath, [fileURLToPath(new URL("./run.mjs", import.meta.url)), path, "one"]);
  assert.equal(cli.status, 2, cli.stderr.toString());
  assert.doesNotMatch(cli.stderr.toString(), /usage:/);
});

test("CLI runs the guest on a stack that holds a million frames", async (t) => {
  const path = join(await temp(t), "recurse.wasm");
  await writeFile(path, recurse());
  const cli = spawnSync(process.execPath, [fileURLToPath(new URL("./run.mjs", import.meta.url)), path]);
  assert.equal(cli.status, 64, cli.stderr.toString());
});
