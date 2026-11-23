// Compile short Python source strings in a native frontend process, or with the frontend built
// as Wasm in this process, then run the resulting bytes in this Node host. Each call has fresh
// Wasm memory and its own set of host tools.
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdtemp, open, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createFileRunner, createRunner } from "./run.mjs";

const home = fileURLToPath(new URL("../", import.meta.url));
const nativeCompiler = fileURLToPath(new URL("../build/wasm/wasm_from_source", import.meta.url));
const wasmCompiler = fileURLToPath(new URL("../build/wasm/wasm_from_source.wasm", import.meta.url));

const linker = fileURLToPath(new URL("./build.sh", import.meta.url));

async function invoke(command, args, input, cwd) {
  const child = spawn(command, args, {
    cwd, env: { ...process.env, PYSTACHY_HOME: process.env.PYSTACHY_HOME ?? home },
    stdio: ["pipe", "pipe", "pipe"],
  });
  const output = [], diagnostics = [];
  child.stdout.on("data", chunk => output.push(chunk));
  child.stderr.on("data", chunk => diagnostics.push(chunk));
  return new Promise((resolve, reject) => {
    child.on("error", reject);
    // Syntax errors can terminate the compiler before a large source write finishes.
    child.stdin.on("error", error => { if (error.code !== "EPIPE") reject(error); });
    child.on("close", (code, signal) => {
      resolve({ code, signal, output: Buffer.concat(output), message: Buffer.concat(diagnostics).toString("utf8").trimEnd() });
    });
    child.stdin.end(input);
  });
}

// The frontend as a WASI command (wasm/build.sh compiler-wasm), compiled once: each call runs it
// on a guest thread that sees the host's files, its source on stdin and its output on stdout.
function wasmInvoker(path) {
  const run = createFileRunner();
  let compiled;
  return async (args, input, cwd) => {
    compiled ??= readFile(path).then(bytes => WebAssembly.compile(bytes)).catch(error => {
      compiled = undefined;
      throw error;
    });
    const module = await compiled;
    const dir = await mkdtemp(join(tmpdir(), "pystachy-compile-"));
    try {
      const [source, out, err] = ["source.py", "out", "err"].map(name => join(dir, name));
      await writeFile(source, input);
      const fds = await Promise.all([open(source, "r"), open(out, "w"), open(err, "w")]);
      let code;
      try {
        code = await run(module, {
          args: ["wasm_from_source", ...args], stdin: fds[0].fd, stdout: fds[1].fd, stderr: fds[2].fd,
          env: { ...process.env, PYSTACHY_HOME: process.env.PYSTACHY_HOME ?? home, PWD: cwd },
        });
      } finally {
        await Promise.all(fds.map(fd => fd.close()));
      }
      return { code, signal: null, output: await readFile(out), message: (await readFile(err, "utf8")).trimEnd() };
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  };
}

function checked(result) {
  if (result.code === 0) return result.output;
  const error = new Error(result.message || `Wasm compilation exited with ${result.signal ?? result.code}`);
  error.code = result.code;
  throw error;
}

// On a direct refusal the native frontend may write the retained LLVM IR on stdout. Only then
// launch the WASI linker. With fallback disabled code 3 exposes the reason to the caller.
// A compiler path ending in .wasm runs in this process; by default, the native frontend, or else
// the Wasm one where only that is built.
export function createCompiler({ compiler, cwd = process.cwd(), fallback = true } = {}) {
  compiler ??= existsSync(nativeCompiler) || !existsSync(wasmCompiler) ? nativeCompiler : wasmCompiler;
  const frontend = compiler.endsWith(".wasm") ? wasmInvoker(compiler)
    : (args, input, at) => invoke(compiler, args, input, at);
  return async source => {
    if (typeof source !== "string") throw new TypeError("expected Python source text");
    let result = await frontend(fallback ? ["-", "-", "-"] : ["-", "-"], source, cwd);
    let refusal = null;
    if (fallback && result.code === 3) {
      refusal = result.message;
      result = await invoke(linker, ["link"], result.output, cwd);
    }
    const module = await WebAssembly.compile(checked(result));
    return { module, backend: refusal === null ? "direct" : "llvm", refusal };
  };
}

export function createCodeMode(options = {}) {
  const compile = createCompiler(options);
  const run = createRunner(options.runtime);
  return async (source, runOptions) => run((await compile(source)).module, runOptions);
}
