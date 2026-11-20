// Runs a WASI (preview 1) command module under Node: node wasm/run.mjs PROGRAM.wasm [ARGS...].
// The program sees its arguments, the environment, and the file system through "/" (the host's,
// read and written as the user who runs node). Its exit status is node's.
import { readFile } from "node:fs/promises";
import { WASI } from "node:wasi";
import process from "node:process";

const [path, ...args] = process.argv.slice(2);
if (!path) {
  process.stderr.write("usage: node wasm/run.mjs PROGRAM.wasm [ARGS...]\n");
  process.exit(2);
}
const wasi = new WASI({
  version: "preview1",
  args: [path, ...args],
  env: { ...process.env, PWD: process.cwd() }, // (wasi_stubs.c starts there)
  preopens: { "/": "/" },
  returnOnExit: true,
});
const module = await WebAssembly.compile(await readFile(path));
const instance = await WebAssembly.instantiate(module, wasi.getImportObject());
let status;
try {
  status = wasi.start(instance);
} catch (e) {
  // a trap (unreachable, out of bounds, stack exhausted): as a native program's crash
  process.stderr.write(`wasm trap: ${e && e.message ? e.message : e}\n`);
  status = 134;
}
process.exitCode = status;
