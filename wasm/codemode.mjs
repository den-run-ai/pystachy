// Compile short Python source strings in a native frontend process, then run the resulting
// bytes in this Node host. Each call has fresh Wasm memory and its own set of host tools.
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { createRunner } from "./run.mjs";

const home = fileURLToPath(new URL("../", import.meta.url));
const nativeCompiler = fileURLToPath(new URL("../build/wasm/wasm_from_source", import.meta.url));

async function compileSource(compiler, source, cwd) {
  const child = spawn(compiler, ["-", "-"], {
    cwd, env: { ...process.env, PYSTACHY_HOME: process.env.PYSTACHY_HOME ?? home },
    stdio: ["pipe", "pipe", "pipe"],
  });
  const binary = [], diagnostics = [];
  child.stdout.on("data", chunk => binary.push(chunk));
  child.stderr.on("data", chunk => diagnostics.push(chunk));
  return new Promise((resolve, reject) => {
    child.on("error", reject);
    // Syntax errors can terminate the compiler before a large source write finishes.
    child.stdin.on("error", error => { if (error.code !== "EPIPE") reject(error); });
    child.on("close", (code, signal) => {
      if (code === 0) return resolve(Buffer.concat(binary));
      const message = Buffer.concat(diagnostics).toString("utf8").trimEnd();
      const error = new Error(message || `Wasm compiler exited with ${signal ?? code}`);
      error.code = code;
      reject(error);
    });
    child.stdin.end(source, "utf8");
  });
}

// Compiler errors reject (code 3 identifies an unsupported typed IR operation). A program that
// runs returns its exit status. The cwd is for resolving source imports, independent of guest mounts.
export function createCodeMode({ compiler = nativeCompiler, runtime, cwd = process.cwd() } = {}) {
  const run = createRunner(runtime);
  return async (source, options) => {
    if (typeof source !== "string") throw new TypeError("expected Python source text");
    return run(await compileSource(compiler, source, cwd), options);
  };
}
