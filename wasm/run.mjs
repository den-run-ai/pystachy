// Runs a WASI (preview 1) program under Node (wasm/README.md):
//   node wasm/run.mjs [--runtime RUNTIME.wasm] PROGRAM.wasm [ARGS...]
// PROGRAM.wasm is a command (wasm/build.sh program), or a module of wasm/tir_wasm.py's, which its
// custom section pystachy.data marks, on the runtime module RUNTIME.wasm (default:
// build/wasm/runtime.wasm, wasm/build.sh runtime-wasm). The program sees its arguments, the
// environment, and the file system through "/" (the host's, as the user who runs node); its
// working directory is node's. Its exit status is node's.
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { WASI } from "node:wasi";
import process from "node:process";

let argv = process.argv.slice(2);
let runtimePath = fileURLToPath(new URL("../build/wasm/runtime.wasm", import.meta.url));
if (argv[0] === "--runtime" && argv.length > 1) {
  runtimePath = argv[1];
  argv = argv.slice(2);
}
const [path, ...args] = argv;
if (!path || path === "--runtime") {
  process.stderr.write("usage: node wasm/run.mjs [--runtime RUNTIME.wasm] PROGRAM.wasm [ARGS...]\n");
  process.exit(2);
}
const trap = (e) => {
  // a trap (unreachable, out of bounds, stack exhausted): as a native program's crash
  process.stderr.write(`wasm trap: ${e && e.message ? e.message : e}\n`);
  return 134;
};
const programModule = await WebAssembly.compile(await readFile(path));
const [section] = WebAssembly.Module.customSections(programModule, "pystachy.data");
const wasi = new WASI({
  version: "preview1",
  args: [path, ...args],
  env: { ...process.env, PWD: process.cwd() }, // (wasi_stubs.c starts there)
  preopens: { "/": "/" },
  // (proc_exit throws, and start() returns its status; on the runtime module, see below)
  returnOnExit: true,
});
if (section === undefined) {
  const instance = await WebAssembly.instantiate(programModule, wasi.getImportObject());
  let status;
  try {
    status = wasi.start(instance);
  } catch (e) {
    status = trap(e);
  }
  process.exitCode = status;
} else {
  // The runtime first (its WASI reactor initialized), then the program, which imports its memory,
  // the block allocated for its data (env.data, whose size pystachy.data holds) and its
  // functions. The runtime calls the program's module code as program.init; it calls
  // pys_obj_eq, pys_obj_cmp and pys_obj_repr only for objects of classes that compare, hash or
  // print through them, which tir_wasm.py refuses.
  const runtimeModule = await WebAssembly.compile(await readFile(runtimePath));
  let program = null;
  const none = (name) => () => { throw new Error(`${name}: the program has no such dispatcher`); };
  const runtime = await WebAssembly.instantiate(runtimeModule, {
    ...wasi.getImportObject(),
    program: { init: () => program.exports.init() },
    env: { pys_obj_eq: none("pys_obj_eq"), pys_obj_cmp: none("pys_obj_cmp"), pys_obj_repr: none("pys_obj_repr") },
  });
  wasi.initialize(runtime);
  const reader = (bytes) => {
    const b = new Uint8Array(bytes);
    let k = 0;
    return () => { // an unsigned LEB128
      let v = 0, shift = 0, x;
      do { x = b[k++]; v += (x & 0x7f) * 2 ** shift; shift += 7; } while (x & 0x80);
      return v;
    };
  };
  const size = reader(section)();
  const data = runtime.exports.malloc(Math.max(size, 8));
  if (data === 0) {
    process.stderr.write("MemoryError: no room for the program's data\n");
    process.exit(1);
  }
  program = await WebAssembly.instantiate(programModule, {
    env: { memory: runtime.exports.memory, data: new WebAssembly.Global({ value: "i32", mutable: false }, data) },
    rt: runtime.exports,
  });
  // the addresses in the program's data, relative to its block until its base is added
  const [relocs] = WebAssembly.Module.customSections(programModule, "pystachy.reloc");
  if (relocs !== undefined) {
    const leb = reader(relocs);
    const view = new DataView(runtime.exports.memory.buffer);
    for (let n = leb(); n > 0; n--) {
      const at = data + leb();
      view.setUint32(at, view.getUint32(at, true) + data, true);
    }
  }
  try {
    process.exitCode = runtime.exports.pys_wasi_run();
  } catch (e) {
    // proc_exit, under returnOnExit, throws a symbol that keys its status on the WASI object
    // (what start() reads); anything else is a trap
    process.exitCode = typeof e === "symbol" && typeof wasi[e] === "number" ? wasi[e] : trap(e);
  }
}
