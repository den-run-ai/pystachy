// Run a WASI command or a typed IR module on Pystachy's shared WASI reactor.
//   node wasm/run.mjs [--runtime RUNTIME.wasm] PROGRAM.wasm [ARGS...]
import { writeSync } from "node:fs";
import { readFile } from "node:fs/promises";
import process from "node:process";
import { pathToFileURL } from "node:url";
import { WASI } from "node:wasi";
import { toolImports } from "./tools.mjs";

const defaultRuntime = new URL("../build/wasm/runtime.wasm", import.meta.url);

async function compile(source) {
  if (source instanceof WebAssembly.Module) return source;
  const bytes = typeof source === "string" || source instanceof URL ? await readFile(source) : source;
  return WebAssembly.compile(bytes);
}

function reader(section) {
  const bytes = new Uint8Array(section);
  let offset = 0;
  return () => {
    let value = 0;
    for (let shift = 0; shift < 35 && offset < bytes.length; shift += 7) {
      const byte = bytes[offset++];
      if (shift === 28 && byte > 15) break;
      value += (byte & 0x7f) * 2 ** shift;
      if ((byte & 0x80) === 0) return value;
    }
    throw new Error("invalid wasm32 integer in Pystachy custom section");
  };
}

function missingDispatcher(name) {
  return () => { throw new Error(`${name}: the program has no such dispatcher`); };
}

// Each runner retains only the compiled runtime module. A path or URL, bytes, or a compiled
// WebAssembly.Module is accepted for both arguments. Each call gets fresh WASI and Wasm state.
// args includes argv[0]. Embedded runs have no directory mounts and borrow their stdio fds.
export function createRunner(runtimeSource = defaultRuntime) {
  return runner(runtimeSource, false);
}

function runner(runtimeSource, cli) {
  let compiledRuntime;
  return async function run(source, {
    args = ["program"], env = {}, stdin = 0, stdout = 1, stderr = 2, tools, preopens,
  } = {}) {
    if (preopens !== undefined) throw new TypeError("directory mounts are unavailable in embedded runs");
    const module = await compile(source);
    const [section] = WebAssembly.Module.customSections(module, "pystachy.data");
    const wasi = new WASI({
      version: "preview1", args, env, preopens: cli ? { "/": "/" } : {}, stdin, stdout, stderr, returnOnExit: true,
    });
    // Keep WASI calls behind JavaScript. Node 22 can crash on direct Wasm fast-API
    // calls into these native functions. The workaround stays local to this instance.
    const io = {};
    for (const [name, fn] of Object.entries(wasi.getImportObject().wasi_snapshot_preview1)) {
      io[name] = (...args) => fn(...args);
    }
    const imports = { wasi_snapshot_preview1: io };
    if (!cli) {
      // Node's WASI uses the actual host descriptors for guest fds 0..2. Only the host may
      // close them. No other descriptors are supplied to embedded runs.
      const close = io.fd_close, renumber = io.fd_renumber;
      const notSupported = 58; // WASI preview1 ENOTSUP
      io.fd_close = (fd) => (fd >>> 0) < 3 ? notSupported : close(fd);
      io.fd_renumber = (from, to) => (from >>> 0) < 3 || (to >>> 0) < 3 ? notSupported : renumber(from, to);
    }
    const trap = (error) => {
      writeSync(stderr, `wasm trap: ${error?.message ?? error}\n`);
      return 134;
    };
    if (section === undefined) {
      const command = new WebAssembly.Instance(module, {
        ...imports,
        codemode: toolImports(tools, () => command.exports.memory),
      });
      try {
        return wasi.start(command);
      } catch (error) {
        return trap(error);
      }
    }

    // Concurrent first calls share compilation, and a failed load can be retried.
    compiledRuntime ??= compile(runtimeSource).catch((error) => {
      compiledRuntime = undefined;
      throw error;
    });
    // A reactor uses initialize(), so WASI.start() cannot handle proc_exit for us.
    const exit = {};
    let status = 0;
    io.proc_exit = (code) => {
      status = code >>> 0;
      throw exit;
    };
    let program;
    const runtime = new WebAssembly.Instance(await compiledRuntime, {
      ...imports,
      codemode: toolImports(tools, () => runtime.exports.memory),
      program: { init: () => program.exports.init() },
      env: {
        pys_obj_eq: missingDispatcher("pys_obj_eq"),
        pys_obj_cmp: missingDispatcher("pys_obj_cmp"),
        pys_obj_repr: missingDispatcher("pys_obj_repr"),
      },
    });
    wasi.initialize(runtime);
    const size = reader(section)();
    const data = runtime.exports.malloc(Math.max(size, 8)) >>> 0;
    if (data === 0) {
      writeSync(stderr, "MemoryError: no room for the program's data\n");
      return 1;
    }
    program = new WebAssembly.Instance(module, {
      env: { memory: runtime.exports.memory, data: new WebAssembly.Global({ value: "i32" }, data) },
      rt: runtime.exports,
    });
    const [relocs] = WebAssembly.Module.customSections(module, "pystachy.reloc");
    if (relocs !== undefined) {
      const leb = reader(relocs);
      const view = new DataView(runtime.exports.memory.buffer);
      for (let n = leb(); n > 0; n--) {
        const offset = leb();
        if (offset + 4 > size) throw new Error("relocation outside Pystachy data");
        const at = data + offset;
        view.setUint32(at, view.getUint32(at, true) + data, true);
      }
    }
    try {
      return runtime.exports.pys_wasi_run();
    } catch (error) {
      return error === exit ? status : trap(error);
    }
  };
}

async function main(argv) {
  let runtime = defaultRuntime;
  if (argv[0] === "--runtime" && argv.length > 1) {
    runtime = argv[1];
    argv = argv.slice(2);
  }
  if (!argv[0] || argv[0] === "--runtime") {
    process.stderr.write("usage: node wasm/run.mjs [--runtime RUNTIME.wasm] PROGRAM.wasm [ARGS...]\n");
    return 2;
  }
  return runner(runtime, true)(argv[0], {
    args: argv,
    env: { ...process.env, PWD: process.cwd() },
  });
}

if (import.meta.main ?? (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url)) {
  process.exitCode = await main(process.argv.slice(2));
}
