export const meta = {
  name: 'pystachy-ffi-design',
  description: 'Panel of FFI designs for Pystachy, adversarial fact checks, judged and synthesized into one recommendation',
  phases: [
    { title: 'Design', detail: '3 independent proposals from different angles' },
    { title: 'Verify', detail: 'adversarially check load-bearing facts and reproduce spike results' },
    { title: 'Judge', detail: '2 judges with distinct lenses score all proposals' },
    { title: 'Synthesize', detail: 'one recommendation, then an adversarial refutation pass' },
  ],
}

const S = '/tmp/claude-0/-home-user-pystachy/291866c5-a7d2-5867-b6e3-d298a0dd7960/scratchpad'

const CONTEXT = `Background. Pystachy (repo at /home/user/pystachy, read only) is a self-hosting compiler for a statically typed subset of Python, written in that subset (pystachy.py). It emits LLVM 18 textual IR. JIT tier: \`pystachy run\` runs opt, then execs lli (ORC) as a separate process with the runtime's object as -extra-object. AOT tier: \`pystachy build\` llvm-links program and runtime bitcode (runtime.c via clang, runtime.py via Pystachy's runtime mode) into a native executable with clang. runtime.c has its own conservative, non-moving, single-threaded mark-sweep GC rooted at @main's frame and a global-roots table; str is UTF-8 bytes; int is checked 64-bit; exceptions use Itanium forced unwinding with pys_personality; __del__ never runs. Contract: a program that compiles prints what CPython prints (documented deviations aside), or is rejected at compile time with file:line: error. The compiler reaches a byte-identical three-stage fixed point, and CI rebuilds it with no Python on PATH; refactors must keep every program's IR byte-identical (irsame). Issue #4 §4 suggests evaluating an AOT CPython-extension mode; docs/typed-ir.md §7.4 sketches it as a third lowering of the typed IR. A planned WebAssembly GC backend forbids raw pointers in runtime.py.

The user's question: "Propose best FFI mechanism for pystachy following latest compiler, runtime, interop best practices with minimal impact that could maybe work with CPython bidirectionally. Only recommend, JIT or AOT or both." Today is 2026-10-09.

Stage 1 already ran 8 research agents (repo ABI map, documented constraints, the 2026 CPython C API, peer compilers, LLVM JIT/AOT, GC interop) and two empirical prototypes. READ ${S}/stage1/digest.txt first (summaries and implications of all 8). The full findings with evidence and open questions are in ${S}/stage1/full.json. The prototypes' working files are in ${S}/spike_ext, ${S}/spike_embed, ${S}/web-capi/exp (pure-IR abi3t modules tested on python-build-standalone CPython 3.15 builds in ${S}/web-capi/pythons), ${S}/web-llvm and ${S}/repo-abi. Do not modify /home/user/pystachy. Scratch work goes under ${S}/stage2/<your-label>.`

const PROPOSAL = {
  type: 'object',
  properties: {
    title: { type: 'string' },
    thesis: { type: 'string', description: 'The recommendation in one paragraph' },
    jit_aot_answer: { type: 'string', description: 'Explicit answer: JIT, AOT or both, for each direction, and why' },
    directions: {
      type: 'array',
      description: 'Exactly three entries: Pystachy->C, Pystachy->CPython, CPython->Pystachy',
      items: {
        type: 'object',
        properties: {
          direction: { type: 'string' },
          tier: { type: 'string', description: 'JIT, AOT, both, or later' },
          mechanism: { type: 'string' },
          example: { type: 'string', description: 'What the user writes, as code, and the command they run' },
          runs_under_cpython: { type: 'string', description: 'How the same file still runs under CPython (the oracle)' },
          types_and_marshalling: { type: 'string' },
          lifetimes: { type: 'string' },
          exceptions: { type: 'string' },
          threads_and_gil: { type: 'string' },
        },
        required: ['direction', 'tier', 'mechanism', 'example', 'runs_under_cpython', 'types_and_marshalling', 'lifetimes', 'exceptions', 'threads_and_gil'],
      },
    },
    abi_target: { type: 'string', description: 'Which CPython ABI (abi3 / abi3t / version-specific), minimum version, module init style' },
    glue_form: { type: 'string', description: 'C API calls emitted directly in IR, or a clang-compiled C glue file, or both; and why' },
    changes: {
      type: 'object',
      properties: {
        runtime_c: { type: 'string' },
        compiler: { type: 'string' },
        driver: { type: 'string' },
        new_files: { type: 'string' },
        estimated_lines: { type: 'string' },
      },
      required: ['runtime_c', 'compiler', 'driver', 'new_files', 'estimated_lines'],
    },
    invariants: { type: 'string', description: 'How each hard invariant is kept: contract, fixed point, Python-free build, irsame/pay-for-use, UBSan/GC-stress, Wasm GC' },
    rejected_at_compile_time: { type: 'array', items: { type: 'string' } },
    stages: {
      type: 'array',
      items: {
        type: 'object',
        properties: { name: { type: 'string' }, deliverable: { type: 'string' }, acceptance: { type: 'string' } },
        required: ['name', 'deliverable', 'acceptance'],
      },
    },
    not_recommended: { type: 'array', items: { type: 'string' }, description: 'Alternatives rejected, each with the reason' },
    risks: { type: 'array', items: { type: 'string' } },
  },
  required: ['title', 'thesis', 'jit_aot_answer', 'directions', 'abi_target', 'glue_form', 'changes', 'invariants', 'rejected_at_compile_time', 'stages', 'not_recommended', 'risks'],
}

const ANGLES = [
  { key: 'minimal-impact', lens: `Your angle: MINIMAL IMPACT. Find the smallest set of changes, in the fewest files, that delivers a usable FFI to C and interop with CPython in both directions, staged so that each stage is independently useful and mergeable. Prefer reusing what exists (runtime mode's extern mechanism, the RUNTIME table, files_sweep as a finalization precedent, the try/landing-pad lowering, the existing llvm-link/clang pipeline, lli flags) over anything new. Count lines honestly.` },
  { key: 'contract-first', lens: `Your angle: CONTRACT FIRST. Pystachy's identity is "same output as CPython, or a compile-time error", plus self-hosting to a byte-identical fixed point, a Python-free build, and pay-for-use features (programs that do not use a feature keep byte-identical IR). Design the FFI so that every program that uses it still runs under CPython with the same output (the oracle), and everything the boundary cannot keep faithful (64-bit int, byte-indexed str, aliasing of copied containers, release timing of Python objects, output interleaving, exceptions) is either checked at the boundary, rejected at compile time with a precise message, or listed as a documented deviation. Be specific about which.` },
  { key: 'state-of-the-art', lens: `Your angle: STATE OF THE ART AND PERFORMANCE. Align with where CPython's C API is going as of October 2026 (Stable ABI, the free-threaded stable ABI, the new module export hook, vectorcall, handle-based APIs), with what the best peers do (PyO3, nanobind, Codon, Mojo, LPython, Julia's PythonCall, pythonnet), and with Pystachy's future backends (typed-IR §7.4 lowering, Wasm GC). Optimize call overhead, start-up and the developer loop (e.g. compile on import with a cache, as mojo.importer and LPython's @lpython do), and say precisely where JIT helps and where AOT is required. Do not sacrifice minimal impact for features that can come later: stage them.` },
]

const VERIFY = {
  type: 'object',
  properties: {
    checks: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          claim: { type: 'string' },
          verdict: { type: 'string', enum: ['confirmed', 'refuted', 'partly', 'unverified'] },
          evidence: { type: 'string', description: 'URL, file:line, or the command run and its output' },
          correction: { type: 'string', description: 'The corrected statement, if refuted or partly' },
        },
        required: ['claim', 'verdict', 'evidence', 'correction'],
      },
    },
    summary: { type: 'string' },
  },
  required: ['checks', 'summary'],
}

const VERIFIERS = [
  { key: 'verify-capi', prompt: `Adversarially verify the CPython C API claims stage 1 relies on. For each, try to REFUTE it from primary sources (peps.python.org including each PEP's Status field, docs.python.org/3.15 and /3.14 "What's New" and the C API pages, github.com/python/cpython tags and Misc/stable_abi.toml, discuss.python.org, hpyproject.org / github.com/hpyproject). Load WebSearch and WebFetch with ToolSearch ("select:WebSearch,WebFetch"). You may also inspect the python-build-standalone 3.15 builds in ${S}/web-capi/pythons (headers, stable_abi lists, python -VV). Default to "unverified" when you cannot find a primary source. Claims:
1. CPython 3.15.0 final was released on or about 2026-10-09 (PEP 790 schedule) — or what the latest released 3.15 build is today.
2. PEP 803 (abi3t, a stable ABI for free-threaded builds) is accepted and implemented in 3.15: Py_TARGET_ABI3T, .abi3t.so naming, PyObject opaque, Py_INCREF/Py_DECREF/Py_TYPE/Py_None compile to function calls.
3. PEP 793 (PyModExport_<name> export hook) is accepted and in 3.15; abi3t requires it and a mandatory Py_mod_abi slot; PEP 820 (PySlot) exists and its status.
4. PyLong_AsInt64/PyLong_FromInt64 are in the Limited API from 3.14; PEP 757 import/export is in the Limited API from 3.15; PyCriticalSection and PEP 788 thread-attach calls are limited in 3.15; PyUnicodeWriter, PyBytesWriter, PyTuple_FromArray and PyInitConfig are not limited.
5. PEP 809 (abi2026) is still a Draft; HPy declared itself unmaintained in September 2026 and points to a draft "PyNI" proposal.
6. Py_mod_gil = Py_MOD_GIL_USED on a free-threaded build re-enables the GIL with a RuntimeWarning (and how a free-threaded 3.13/3.14 build treats an abi3 module at all: can it load abi3 .so files?).
7. Py_IncRef/Py_DecRef, Py_GetConstantBorrowed, PyErr_GetRaisedException/PyErr_SetRaisedException, PyObject_Vectorcall, PyType_GetFlags, PyCapsule_New, PyType_FromSpec, PyObject_GetTypeData, PyWeakref_GetRef, PyUnicode_AsUTF8AndSize, PyModule_FromDefAndSpec / PyModuleDef_Init are part of the Stable ABI, and since which version each.
8. Python 3.13+ / 3.14 support status of the Limited API on free-threaded builds (whether abi3 wheels can be used on 3.14t).
Also give the support window: which CPython versions are in bugfix/security support on 2026-10-09, to settle the minimum version to target.` },
  { key: 'verify-llvm-spikes', prompt: `Adversarially verify the LLVM and prototype claims stage 1 relies on, by re-running things on this machine (clang-18, lli-18, opt-18, llvm-link-18, Python 3.13 with headers, /usr/lib/x86_64-linux-gnu/libpython3.13.so) and by reading primary sources (llvm.org docs, github.com/llvm/llvm-project, llvmlite docs/changelog; load WebSearch and WebFetch with ToolSearch "select:WebSearch,WebFetch"). Try to REFUTE each claim; default to "unverified" if you cannot check it. Claims:
1. lli-18 has a -dlopen (and -load) option that dlopens a library RTLD_GLOBAL so JIT'd IR can call it, and -extra-object; JIT'd IR that embeds CPython via libpython3.13.so runs (Py_Initialize, import math, call, finalize). Reproduce a minimal case yourself from scratch in ${S}/stage2/verify-llvm-spikes.
2. The spike_ext prototype: an AOT extension module built from Pystachy IR plus runtime bitcode, internalized except PyInit, loads in CPython 3.13 and calls cost about 24 ns versus about 250 ns through ctypes; under GC stress it is correct only with the runtime changes (pys_enter/pys_leave, pin table). Re-run its build and tests from ${S}/spike_ext (read build_ext.sh, libify.py, ext_test.py and runtime_lib.diff if present) and report what reproduces, including whether 40/40 tests stayed byte-identical with the modified runtime (re-run a sample yourself if feasible within reasonable time: e.g. 10 tests/*.py programs through the CPython-hosted compiler with the original and the modified runtime).
3. Forced unwinding of a Pystachy exception through CPython's C frames is harmful (skips cleanup; one test reported leaked references and RecursionError after ~1000 crossings) — so every boundary needs a catch-all landing pad. Check the evidence in ${S}/web-llvm and ${S}/web-gc, and reason about CPython 3.13's frames (do its C files have unwind tables? -fexceptions? -fasynchronous-unwind-tables default on x86-64 Linux).
4. The LLVM ABI-lowering library (llvm/lib/ABI) status: only x86-64 SysV and BPF, behind an experimental clang flag, no C API, as of the latest LLVM release in October 2026. And which LLVM version is the latest release today.
5. llvmlite's latest release, the LLVM version it bundles, and its ORC/JITLink support; whether the system libLLVM-18 exports the ORC LLJIT C API (nm -D) and the claim that in-process LLJIT through ctypes needs libgcc_s preloaded RTLD_GLOBAL.
6. Native TLS in a runtime object passed with -extra-object is silently wrong under lli-18 without the ORC runtime (check whether runtime.c uses _Thread_local or __thread today: grep it).
7. User programs cannot declare externs today: in runtime mode only (pystachy.py near 8015-8020 and 10925-10945); a \`def f(x: int) -> int: ...\` in a user program compiles to something that raises or returns None. Check by compiling a tiny example with python3 /home/user/pystachy/pystachy.py ir.
8. Decorators are rejected for user functions except a known set (pystachy.py near 8037-8041): which decorators are accepted today?
Report each with the commands you ran and their outputs.` },
]

const JUDGE = {
  type: 'object',
  properties: {
    scores: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          proposal: { type: 'string' },
          minimal_impact: { type: 'number', description: '1-10' },
          contract_and_invariants: { type: 'number', description: '1-10' },
          interop_correctness: { type: 'number', description: '1-10: refcounts, GC roots, exceptions, GIL, cycles' },
          currency_2026: { type: 'number', description: '1-10: aligned with current CPython/LLVM practice' },
          evidence: { type: 'number', description: '1-10: backed by the prototypes and sources' },
          total: { type: 'number' },
          fatal_flaws: { type: 'array', items: { type: 'string' } },
        },
        required: ['proposal', 'minimal_impact', 'contract_and_invariants', 'interop_correctness', 'currency_2026', 'evidence', 'total', 'fatal_flaws'],
      },
    },
    winner: { type: 'string' },
    grafts: { type: 'array', items: { type: 'string' }, description: 'The best ideas from the other proposals to graft onto the winner' },
    must_fix: { type: 'array', items: { type: 'string' }, description: 'Errors or gaps the final recommendation must fix' },
    rationale: { type: 'string' },
  },
  required: ['scores', 'winner', 'grafts', 'must_fix', 'rationale'],
}

const JUDGES = [
  { key: 'judge-maintainer', lens: `You judge as Pystachy's maintainer: the invariants (contract, three-stage fixed point, Python-free build, irsame and pay-for-use, UBSan and GC stress in make verify), blast radius in pystachy.py and runtime.c, the Wasm GC constraint on runtime.py, the typed-IR roadmap (§7.4 needs step 16 and recoverable elaboration), and whether each stage is a reviewable, mergeable PR. Read the relevant code yourself where a proposal makes a claim about it.` },
  { key: 'judge-interop', lens: `You judge as a veteran of bidirectional runtime interop (pythonnet, PyO3, nanobind, JPype, PythonCall.jl, Pyodide): reference ownership, GC roots for objects held across heaps, deferred decref under the GIL, exception firewalls, re-entrancy and the stack-bottom problem for a conservative collector, threads/GIL/free-threading, shutdown order, cross-heap cycles, multiple extension modules in one process, and alignment with the CPython C API's direction in 2026 (use the verification results). Penalize anything that would crash, leak unboundedly, or silently diverge from CPython.` },
]

phase('Design')
const proposalsP = parallel(ANGLES.map(a => () =>
  agent(`${CONTEXT}\n\n${a.lens}\n\nProduce one complete FFI recommendation for Pystachy covering all three directions (Pystachy calls C; Pystachy calls CPython; CPython calls Pystachy), with an explicit JIT / AOT / both answer per direction. Ground every claim in the stage-1 evidence or the code (file:line); where stage 1 disagrees with itself, resolve it (you may run small experiments in your scratch dir). The example field must show real code a user would write.`,
    { label: `design:${a.key}`, phase: 'Design', schema: PROPOSAL })
    .then(p => p ? { key: a.key, ...p } : null)))

const verifiesP = parallel(VERIFIERS.map(v => () =>
  agent(`${CONTEXT}\n\n${v.prompt}`, { label: v.key, phase: 'Verify', schema: VERIFY })
    .then(r => r ? { key: v.key, ...r } : null)))

const [proposalsRaw, verifiesRaw] = await Promise.all([proposalsP, verifiesP])
const proposals = proposalsRaw.filter(Boolean)
const verifies = verifiesRaw.filter(Boolean)
log(`${proposals.length} proposals, ${verifies.length} verification reports`)

const propText = JSON.stringify(proposals, null, 1)
const verText = JSON.stringify(verifies, null, 1)

phase('Judge')
const judgments = (await parallel(JUDGES.map(j => () =>
  agent(`${CONTEXT}\n\n${j.lens}\n\nScore each of these ${proposals.length} FFI proposals (by its key) and pick a winner. Use the verification results to penalize claims that were refuted. Name the best ideas to graft from the losers and everything the final recommendation must fix.\n\nPROPOSALS:\n${propText}\n\nVERIFICATION RESULTS:\n${verText}`,
    { label: j.key, phase: 'Judge', schema: JUDGE })
    .then(r => r ? { key: j.key, ...r } : null)))).filter(Boolean)

phase('Synthesize')
const FINAL = {
  ...PROPOSAL,
  properties: {
    ...PROPOSAL.properties,
    corrections_applied: { type: 'array', items: { type: 'string' }, description: 'Refuted or corrected facts and judge must-fixes, and how each was handled' },
    deviations_to_document: { type: 'array', items: { type: 'string' } },
    open_decisions_for_maintainer: { type: 'array', items: { type: 'string' } },
  },
  required: [...PROPOSAL.required, 'corrections_applied', 'deviations_to_document', 'open_decisions_for_maintainer'],
}

const synthPrompt = (extra) => `${CONTEXT}\n\nWrite the single final FFI recommendation for Pystachy. Start from the judges' winner, graft the ideas they named, fix every must-fix, and apply every verification correction (never repeat a refuted claim; mark anything still unverified). Keep it minimal-impact and staged, and give an explicit JIT / AOT / both answer per direction. Be concrete: real user code in the examples, file:line for the code it touches, honest line estimates.\n\nPROPOSALS:\n${propText}\n\nVERIFICATION RESULTS:\n${verText}\n\nJUDGMENTS:\n${JSON.stringify(judgments, null, 1)}${extra}`

let final = await agent(synthPrompt(''), { label: 'synthesize', phase: 'Synthesize', schema: FINAL })

const REFUTE = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['sound', 'needs_revision'] },
    blocking: { type: 'array', items: { type: 'object', properties: { issue: { type: 'string' }, why: { type: 'string' }, fix: { type: 'string' } }, required: ['issue', 'why', 'fix'] } },
    nonblocking: { type: 'array', items: { type: 'string' } },
  },
  required: ['verdict', 'blocking', 'nonblocking'],
}

const refutation = await agent(`${CONTEXT}\n\nTry hard to REFUTE this final FFI recommendation for Pystachy. Look for: a claim contradicted by the code (check file:line yourself), by the verification results or by the prototypes; a stage that would break an invariant (contract, fixed point, Python-free build, irsame/pay-for-use, Wasm GC); a lifetime, GC-root, exception, GIL or re-entrancy hole that would crash, leak unboundedly or silently diverge from CPython; a JIT/AOT answer that does not follow from the evidence; an example that would not run under CPython; and an important alternative it dismisses wrongly. Only call something blocking if it is a real error, not a preference.\n\nVERIFICATION RESULTS:\n${verText}\n\nFINAL RECOMMENDATION:\n${JSON.stringify(final, null, 1)}`,
  { label: 'refute', phase: 'Synthesize', schema: REFUTE })

if (refutation && refutation.verdict === 'needs_revision' && refutation.blocking.length) {
  log(`refuter found ${refutation.blocking.length} blocking issue(s); revising`)
  const revised = await agent(synthPrompt(`\n\nYOUR PREVIOUS DRAFT:\n${JSON.stringify(final, null, 1)}\n\nA REFUTER FOUND THESE BLOCKING ISSUES. Verify each against the code and evidence; fix the real ones, and record in corrections_applied which you fixed and which you rejected and why:\n${JSON.stringify(refutation, null, 1)}`),
    { label: 'revise', phase: 'Synthesize', schema: FINAL })
  if (revised) final = revised
}

return { final, refutation, judgments, verifies, proposals }
