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

// runtime.c's tracebacks: the engine's stack, which only the host can read. trace keeps the stack
// of a raise; frames gives the kept one's, or the current stack's, program frames, innermost
// first, each as its call's offset in the program's module (the frames whose module is not the
// one calling these imports); lines copies the program's pystachy.lines section (tir_wasm.py).
function traceImports(program, getMemory) {
  const [lines] = WebAssembly.Module.customSections(program, "pystachy.lines");
  let kept;
  function capture() {
    const limit = Error.stackTraceLimit;
    const holder = {};
    Error.stackTraceLimit = 5000; // (the runtime keeps 4,096 frames, as on native builds)
    try {
      Error.captureStackTrace(holder, capture);
    } finally {
      Error.stackTraceLimit = limit;
    }
    return holder; // (V8 formats holder.stack when it is first read)
  }
  function offsets(holder) {
    const prepare = Error.prepareStackTrace;
    let sites;
    Error.prepareStackTrace = (_, callSites) => callSites;
    try {
      sites = holder.stack;
    } finally {
      Error.prepareStackTrace = prepare;
    }
    const wasm = sites.filter((site) => site.getFileName()?.startsWith("wasm:"));
    const caller = wasm[0]?.getFileName();
    return wasm.filter((site) => site.getFileName() !== caller).map((site) => site.getPosition());
  }
  return {
    trace() {
      if (lines !== undefined) kept = capture();
    },
    frames(fromKept, at, max) {
      const found = offsets(fromKept && kept !== undefined ? kept : capture()).slice(0, max >>> 0);
      new Uint32Array(getMemory().buffer, at >>> 0, found.length).set(found);
      return found.length;
    },
    lines(to, size) {
      if (lines === undefined) return 0;
      if (to !== 0 && size >>> 0 === lines.byteLength) new Uint8Array(getMemory().buffer, to >>> 0, size >>> 0).set(new Uint8Array(lines));
      return lines.byteLength;
    },
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
  async function run(source, {
    args = ["program"], env = {}, stdin = 0, stdout = 1, stderr = 2, tools, preopens, executionTimeoutMs,
  } = {}) {
    if (preopens !== undefined) throw new TypeError("directory mounts are unavailable in embedded runs");
    const module = await compile(source);
    const [section] = WebAssembly.Module.customSections(module, "pystachy.data");
    let runtimeModule;
    if (section !== undefined) {
      // Concurrent first calls share compilation, and a failed load can be retried.
      compiledRuntime ??= compile(runtimeSource).catch((error) => {
        compiledRuntime = undefined;
        throw error;
      });
      runtimeModule = await compiledRuntime;
    }
    const options = { args, env, stdin, stdout, stderr, tools };
    if (executionTimeoutMs === undefined) return instantiateAndRun(module, section, runtimeModule, options);
    // V8 can interrupt synchronous Wasm and JS across this call. Loading and
    // compilation have already finished. A blocking native host call can delay return.
    const { runInNewContext } = await import("node:vm");
    const execute = () => instantiateAndRun(module, section, runtimeModule, options);
    return runInNewContext("execute()", { execute }, { timeout: executionTimeoutMs });
  }

  function instantiateAndRun(module, section, runtimeModule, { args, env, stdin, stdout, stderr, tools }) {
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
        pystachy: traceImports(module, () => command.exports.memory),
      });
      try {
        return wasi.start(command);
      } catch (error) {
        return trap(error);
      }
    }

    // A reactor uses initialize(), so WASI.start() cannot handle proc_exit for us.
    const exit = {};
    let status = 0;
    io.proc_exit = (code) => {
      status = code >>> 0;
      throw exit;
    };
    const hasHandlers = WebAssembly.Module.customSections(module, "pystachy.eh").length > 0;
    if (hasHandlers && !WebAssembly.Module.imports(runtimeModule).some(
      ({ module, name, kind }) => module === "program" && name === "raise" && kind === "function",
    )) {
      throw new Error("this program requires a runtime with catchable exceptions. Rebuild with wasm/build.sh runtime-wasm");
    }
    const tag = hasHandlers ? new WebAssembly.Tag({ parameters: ["i32"] }) : undefined;
    let program;
    // The runtime rethrows an escaped exception once to start its uncaught report.
    // Only that first unwind falls through to C. Python called by the report or
    // by pys_finish (including atexit) still uses the guest's catchable tag.
    let reportUnwind = false;
    const runtime = new WebAssembly.Instance(runtimeModule, {
      ...imports,
      codemode: toolImports(tools, () => runtime.exports.memory),
      pystachy: traceImports(module, () => runtime.exports.memory),
      program: {
        raise(pointer) {
          if (reportUnwind) reportUnwind = false;
          else if (hasHandlers) throw new WebAssembly.Exception(tag, [pointer]);
        },
        init() {
          if (hasHandlers) runtime.exports.pys_eh_on();
          program.exports.init();
        },
      },
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
      env: {
        memory: runtime.exports.memory, data: new WebAssembly.Global({ value: "i32" }, data), pystachy_exception: tag,
      },
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
      if (!hasHandlers) return runtime.exports.pys_wasi_run();
      const stack = runtime.exports.__stack_pointer;
      const entryStack = stack.value;
      let uncaught;
      for (;;) {
        try {
          if (uncaught === undefined) return runtime.exports.pys_wasi_run();
          reportUnwind = true;
          runtime.exports.pys_throw(uncaught); // noreturn
          throw new Error("pys_throw returned from uncaught exception handling");
        } catch (error) {
          if (!(error instanceof WebAssembly.Exception && error.is(tag))) throw error;
          uncaught = error.getArg(tag, 0);
          stack.value = entryStack; // unwinding skipped the C stack epilogues
        }
      }
    } catch (error) {
      return error === exit ? status : trap(error);
    }
  }
  return run;
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
