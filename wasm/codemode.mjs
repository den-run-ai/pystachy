// Compile short Python source strings in a native frontend process, then run the resulting
// bytes in this Node host. Each call has fresh Wasm memory and its own set of host tools.
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { createRunner } from "./run.mjs";

const home = fileURLToPath(new URL("../", import.meta.url));
const nativeCompiler = fileURLToPath(new URL("../build/wasm/wasm_from_source", import.meta.url));

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

function checked(result) {
  if (result.code === 0) return result.output;
  const error = new Error(result.message || `Wasm compilation exited with ${result.signal ?? result.code}`);
  error.code = result.code;
  throw error;
}

// On a direct refusal the native frontend may write the retained LLVM IR on stdout. Only then
// launch the WASI linker. With fallback disabled code 3 exposes the reason to the caller.
export function createCodeMode({ compiler = nativeCompiler, runtime, cwd = process.cwd(), fallback = true } = {}) {
  const run = createRunner(runtime);
  return async (source, options) => {
    if (typeof source !== "string") throw new TypeError("expected Python source text");
    let result = await invoke(compiler, fallback ? ["-", "-", "-"] : ["-", "-"], source, cwd);
    if (fallback && result.code === 3) {
      result = await invoke(linker, ["link"], result.output, cwd);
    }
    return run(checked(result), options);
  };
}
