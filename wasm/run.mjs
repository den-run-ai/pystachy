// Run a WASI command or a typed IR module on Pystachy's shared WASI reactor.
//   node wasm/run.mjs [--runtime RUNTIME.wasm] PROGRAM.wasm [ARGS...]
import { writeSync } from "node:fs";
import { readFile } from "node:fs/promises";
import process from "node:process";
import { pathToFileURL } from "node:url";
import { WASI } from "node:wasi";
import {
  isMainThread, MessageChannel, parentPort, receiveMessageOnPort, Worker, workerData,
} from "node:worker_threads";
import { checkTools, toolImports } from "./tools.mjs";

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

// Guests run on worker threads with a 256 MiB stack. V8 allows under 1 MiB on a host's main
// thread: about 11,000 frames of a small recursive function, where Python's limit can allow more.
const STACK_MB = 256;

// Each runner retains only the compiled runtime module. A path or URL, bytes, or a compiled
// WebAssembly.Module is accepted for both arguments. Each call gets fresh WASI and Wasm state.
// args includes argv[0]. Embedded runs have no directory mounts and borrow their stdio fds.
export function createRunner(runtimeSource = defaultRuntime) {
  // (a guest thread takes about 25 ms to start: the first one starts now, while the caller compiles)
  if (idleGuests.length === 0) idleGuests.push(guestThread());
  return runner(runtimeSource, false);
}

// The repository's own tools as Wasm (the source compiler: codemode.mjs) see the host's files, as
// the CLI's programs do. Never give this runner a program that the host does not trust.
export function createFileRunner(runtimeSource = defaultRuntime) {
  if (idleGuests.length === 0) idleGuests.push(guestThread());
  return runner(runtimeSource, false, false, true);
}

// here: run on this thread, which the CLI and guest threads (below) do; files: mount the host's
// root directory, as the CLI does
function runner(runtimeSource, cli, here = cli, files = cli) {
  let compiledRuntime;
  async function run(source, {
    args = ["program"], env = {}, stdin = 0, stdout = 1, stderr = 2, tools, preopens, executionTimeoutMs,
  } = {}) {
    if (preopens !== undefined) throw new TypeError("directory mounts are unavailable in embedded runs");
    checkTools(tools);
    const { runInNewContext } = await import("node:vm");
    // vm validates a deadline as it does for the run's own timer
    if (executionTimeoutMs !== undefined) runInNewContext("0", {}, { timeout: executionTimeoutMs });
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
    if (!here) return onGuestThread(module, runtimeModule, { args, env, stdin, stdout, stderr }, tools, executionTimeoutMs, files);
    const options = { args, env, stdin, stdout, stderr, tools };
    if (executionTimeoutMs === undefined) return instantiateAndRun(module, section, runtimeModule, options);
    // V8 can interrupt synchronous Wasm and JS across this call. Loading and
    // compilation have already finished. A blocking native host call can delay return.
    const execute = () => instantiateAndRun(module, section, runtimeModule, options);
    return runInNewContext("execute()", { execute }, { timeout: executionTimeoutMs });
  }

  function instantiateAndRun(module, section, runtimeModule, { args, env, stdin, stdout, stderr, tools }) {
    const wasi = new WASI({
      version: "preview1", args, env, preopens: files ? { "/": "/" } : {}, stdin, stdout, stderr, returnOnExit: true,
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
    writeSync(2, "usage: node wasm/run.mjs [--runtime RUNTIME.wasm] PROGRAM.wasm [ARGS...]\n");
    return 2;
  }
  return runner(runtime, true)(argv[0], {
    args: argv,
    env: { ...process.env, PWD: process.cwd() },
  });
}

// Embedded runs take an idle guest thread or start one. A thread returns to the pool after a
// run that ended normally, and is ended by a deadline. The caller's thread runs each tool while
// the guest waits for its reply. Idle threads do not keep the process alive.
const idleGuests = [];

function guestThread() {
  const signal = new SharedArrayBuffer(4);
  const { port1, port2 } = new MessageChannel();
  const worker = new Worker(new URL(import.meta.url), {
    workerData: { pystachyGuest: true, signal, replies: port2 }, transferList: [port2],
    resourceLimits: { stackSizeMb: STACK_MB },
  });
  worker.unref();
  return { worker, wake: new Int32Array(signal), replies: port1 };
}

function timedOut(ms) {
  return Object.assign(new Error(`Script execution timed out after ${ms}ms`), { code: "ERR_SCRIPT_EXECUTION_TIMEOUT" });
}

async function onGuestThread(module, runtimeModule, options, tools, timeoutMs, files) {
  const { runInNewContext } = await import("node:vm");
  const guest = idleGuests.pop() ?? guestThread();
  const { worker, wake, replies } = guest;
  worker.ref();
  return new Promise((resolve, reject) => {
    const deadline = timeoutMs === undefined ? undefined : performance.now() + timeoutMs;
    let timer;
    function finish(settle, value, reuse) {
      clearTimeout(timer);
      worker.off("message", message);
      worker.off("error", failed);
      worker.off("exit", exited);
      if (reuse) {
        worker.unref();
        idleGuests.push(guest);
      } else {
        worker.terminate();
      }
      settle(value);
    }
    function stop() {
      finish(reject, timedOut(timeoutMs), false);
    }
    function message(m) {
      if (m.tool === undefined) {
        if (m.error === undefined) finish(resolve, m.status, true);
        else finish(reject, Object.assign(new Error(m.error.message), m.error.code ? { code: m.error.code } : {}), true);
        return;
      }
      // a deadline also interrupts a tool that is still running when it passes
      const call = () => tools.get(m.tool)(m.payload);
      try {
        const value = deadline === undefined ? call()
          : runInNewContext("call()", { call }, { timeout: Math.max(1, Math.ceil(deadline - performance.now())) });
        try {
          replies.postMessage({ value });
        } catch {
          replies.postMessage({ value: undefined });
        }
      } catch (error) {
        if (error?.code === "ERR_SCRIPT_EXECUTION_TIMEOUT") return stop();
        replies.postMessage({ error: String(error?.message ?? error) });
      }
      Atomics.store(wake, 0, 1);
      Atomics.notify(wake, 0);
    }
    function failed(error) {
      finish(reject, error, false);
    }
    function exited(code) {
      finish(reject, new Error(`the guest thread exited with status ${code}`), false);
    }
    worker.on("message", message);
    worker.on("error", failed);
    worker.on("exit", exited);
    const names = tools === undefined ? undefined : [...tools].filter(([, f]) => typeof f === "function").map(([n]) => n);
    worker.postMessage({ module, runtimeModule, options, names, files });
    if (timeoutMs !== undefined) timer = setTimeout(stop, timeoutMs);
  });
}

// A guest thread: each tool call posts the request, then blocks until the caller's thread
// replies, so the guest's synchronous import returns the tool's result.
function serveGuests({ signal, replies }) {
  const wake = new Int32Array(signal);
  parentPort.on("message", ({ module, runtimeModule, options, names, files }) => {
    const tools = names === undefined ? undefined : new Map(names.map((name) => [name, (payload) => {
      parentPort.postMessage({ tool: name, payload });
      Atomics.wait(wake, 0, 0);
      Atomics.store(wake, 0, 0);
      const reply = receiveMessageOnPort(replies).message;
      if (reply.error !== undefined) throw new Error(reply.error);
      return reply.value;
    }]));
    runner(runtimeModule, false, true, files)(module, { ...options, tools }).then(
      (status) => parentPort.postMessage({ status }),
      (error) => parentPort.postMessage({ error: { message: String(error?.message ?? error), code: error?.code } }),
    );
  });
}

// The CLI also runs its guest on such a thread. The guest's stdio is the process's descriptors either way.
if (!isMainThread && workerData?.pystachyGuest) {
  serveGuests(workerData);
} else if (!isMainThread && workerData?.pystachyRun) {
  process.exit(await main(workerData.argv));
} else if (import.meta.main ?? (process.argv[1] && pathToFileURL(process.argv[1]).href === import.meta.url)) {
  const worker = new Worker(new URL(import.meta.url), {
    workerData: { pystachyRun: true, argv: process.argv.slice(2) }, resourceLimits: { stackSizeMb: STACK_MB },
  });
  worker.on("error", (error) => writeSync(2, `${error?.stack ?? error}\n`));
  process.exitCode = await new Promise((resolve) => worker.on("exit", resolve));
}
