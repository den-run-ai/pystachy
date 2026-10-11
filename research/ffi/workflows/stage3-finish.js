export const meta = {
  name: 'pystachy-ffi-finish',
  description: 'Port the FFI prototype onto current main, finish fixes and verification, refute it, and write the final recommendation',
  phases: [
    { title: 'Port', detail: 'rebase the prototype onto origin/main, fix probes and nonblocking items, full verification' },
    { title: 'Refute', detail: '3 refuters with distinct lenses' },
    { title: 'Fix', detail: 'only if a refuter finds real blocking issues' },
    { title: 'Write', detail: 'final recommendation document' },
  ],
}

const S = '/tmp/claude-0/-home-user-pystachy/291866c5-a7d2-5867-b6e3-d298a0dd7960/scratchpad'
const T = `${S}/stage3/tree`

const CONTEXT = `Background. Pystachy (/home/user/pystachy; treat it as READ ONLY: it is on branch claude/ffi-research and must not change) is a self-hosting compiler for a statically typed subset of Python that emits LLVM 18 IR. JIT tier: \`pystachy run\` execs lli as a separate process; AOT tier: \`pystachy build\` llvm-links program and runtime bitcode and links with clang. runtime.c has a conservative, non-moving, single-threaded GC. Contract: a program that compiles prints what CPython prints (documented deviations aside), or is rejected at compile time with file:line: error. The compiler reaches a byte-identical three-stage fixed point; CI rebuilds it with no Python on PATH; programs that do not use a feature must keep byte-identical IR (make irsame).

The user's question: "Propose best FFI mechanism for pystachy following latest compiler, runtime, interop best practices with minimal impact that could maybe work with CPython bidirectionally. Only recommend, JIT or AOT or both." Today is 2026-10-11.

State so far (all under ${S}):
- stage1/digest.txt and stage1/full.json: 8 research agents (repo ABI, constraints, CPython C API 2026, peers, LLVM, GC interop, 2 spikes).
- stage2out/proposals.json, verifications.json, judgments.json (both judges chose the minimal-impact design), synthesis_draft.json (the draft recommendation: S0 decision record; S1 @ffi.extern for C, JIT and AOT; S2 lib/pyobj.py embedding CPython, JIT and AOT; S3 \`pystachy ext\` abi3 (3.12+) and abi3t (3.15+) extension modules, AOT only; S4-S6 later), refutation.json (4 blocking issues, 13 nonblocking).
- stage2/final/tree3: the draft's prototype revised for the 4 blocking issues (ext environment: __name__, sys.argv, print failure, re-exec after failure; picklable exports via per-export trampolines with the module as self; depth-guarded automatic release of Python references; a program's own ffi.py shadows the builtin). It is based on the OLD main, commit cbab8c3. Its verification there: make fixed point OK, tests/run.sh 1886 passed 0 failed, irsame 1265/1265 same, check_runtime and rtabi OK, UBSan trap mode mostly same, but the FFI probes gave "61 same, 13 different" (stage2/final/probe3-native.log; e.g. the pickling probe pk3 under multiprocessing interleaves child output), and the 13 nonblocking items in stage2out/refutation.json are not done. Scripts: stage2/final/all3.sh, probe3.sh, ubsan3.sh, irsame.sh, corpus.txt, fx/, run3/. The diffs against cbab8c3: stage2/final/tree3-{pystachy.py,runtime.c,rtabi.py,check_runtime.py}.diff; new files in tree3: lib/pyobj.py, pyext.c, pyembed.c, tools/rt_cpython/ffi.py, tools/rt_cpython/pyobj.py.
- CPython builds for probes: /usr/bin/python3 (3.13.16, with libpython3.13.so and headers), /usr/bin/python3.12, and python-build-standalone builds under ${S}/stage2/capi-verify/ (py313t, py314, py314t, py315, py315t, pythons/) and ${S}/web-capi/pythons/ (3.15.0b4 and 3.15t). Find each interpreter's bin/python3.

Since then main moved from cbab8c3 to 3542d63 (32 commits): pystachy.py about +275 lines (the lli command is now near pystachy.py:16732), runtime.c +74 (SIGXFSZ ignored, empty lists release storage, with-file cleanup without try: programs with try OR with now turn exceptions on), tests/run.sh rewritten as a work queue, \`python3 -m pystachy\` as the hosted launcher, a new \`make lint\` (ruff via ruff.toml, shellcheck, clang warnings) and a Lint workflow, verify.sh changes, new tests. Open issue #108 (architecture: compiled dynamic values vs a bytecode interpreter) says typed/dynamic adapters should start with scalars, not copied mutable containers, and names #4's CPython-hosted compiled functions as the alternative for package access.`

const PORT = {
  type: 'object',
  properties: {
    base_commit: { type: 'string' },
    head_commit: { type: 'string' },
    patch_path: { type: 'string', description: 'git diff base..head written to a file' },
    diffstat: { type: 'string' },
    checks: {
      type: 'array',
      items: {
        type: 'object',
        properties: { check: { type: 'string' }, command: { type: 'string' }, result: { type: 'string' }, pass: { type: 'boolean' } },
        required: ['check', 'command', 'result', 'pass'],
      },
    },
    probe_summary: { type: 'string', description: 'Per CPython version and tier: same/different counts, and every remaining difference with its cause' },
    nonblocking: {
      type: 'array',
      items: {
        type: 'object',
        properties: { item: { type: 'string' }, action: { type: 'string', enum: ['fixed', 'documented', 'rejected'] }, detail: { type: 'string' } },
        required: ['item', 'action', 'detail'],
      },
    },
    design_changes: { type: 'array', items: { type: 'string' }, description: 'Anything that changes the recommendation itself relative to synthesis_draft.json' },
    measurements: { type: 'array', items: { type: 'string' }, description: 'Call cost, import time, build time, binary size, measured on the ported tree' },
    remaining_issues: { type: 'array', items: { type: 'string' } },
  },
  required: ['base_commit', 'head_commit', 'patch_path', 'diffstat', 'checks', 'probe_summary', 'nonblocking', 'design_changes', 'measurements', 'remaining_issues'],
}

phase('Port')
const port = await agent(`${CONTEXT}

Your task: bring the prototype to a finished, verified state on the CURRENT main, then report.

1. Make a private clone (never touch /home/user/pystachy's working tree, index or branches):
   git clone -q /home/user/pystachy ${T} && cd ${T} && git fetch -q /home/user/pystachy refs/remotes/origin/main:refs/heads/base && git checkout -q -b ffi cbab8c3
   Copy stage2/final/tree3's changed and new files over it (only the files that differ from cbab8c3: pystachy.py, runtime.c, tools/rtabi.py, tools/check_runtime.py, lib/pyobj.py, pyext.c, pyembed.c, tools/rt_cpython/ffi.py, tools/rt_cpython/pyobj.py; not the *.orig/*.s12/*.s3a/*.s1 backups or patch1.py), commit, then \`git rebase base\` and resolve every conflict by hand, keeping main's behaviour and the prototype's additions. Check that the rebased diff (git diff base..ffi) contains only FFI work.
2. Finish the work: make all 13 probe differences in stage2/final/probe3-native.log match (fix the cause; if a probe itself was wrong, fix the probe and say why), and handle each of the 13 nonblocking items in ${S}/stage2out/refutation.json: fix it, or document it as a deviation or limitation where the design says so, or reject it with a reason. Keep everything pay-for-use: programs that do not use the FFI must keep byte-identical IR against base.
3. Verify on the rebased tree, with real commands, recording each: \`make\` (three-stage fixed point, and runtime.py's fixed point); runtime.py's IR identical to base's compiler's; \`python3 tools/check_runtime.py\`; \`python3 tools/rtabi.py ./pystachy\` (or whatever main's Makefile runs); \`tests/run.sh ./pystachy\` (JIT and AOT, all pass); \`make irsame REF=base\` (every corpus program identical; this builds base's compiler under build/ref); \`make check-ir\`; \`make lint\` (ruff is at /root/.local/bin/ruff; if shellcheck is missing, try pip install --user shellcheck-py, otherwise report it as not run); the FFI probes (adapt probe3.sh, ubsan3.sh and all3.sh to the new tree and paths) on every available CPython: 3.11 if present (below the floor: must fail cleanly), 3.12, 3.13, 3.13t, 3.14, 3.14t, 3.15 and 3.15t, JIT and AOT where the stage applies, plus GC stress (PYSTACHY_GC_STRESS) and UBSan trap mode. If time allows, run \`make verify\` in the background (it takes 20-30 minutes) and report its result; say if you did not.
4. Measure on the final tree: the per-call cost of an exported function (vs ctypes and vs pure Python), extension import time, \`pystachy ext\` build time with a warm runtime cache, .so size, and the JIT start-up cost with -dlopen of libpython.
5. Write git diff base..ffi to ${S}/stage3/ffi-prototype.patch and the logs under ${S}/stage3/logs/. Leave the clone in place.
Report honestly: anything that still fails goes in remaining_issues with its cause.`,
  { label: 'port-and-verify', phase: 'Port', schema: PORT })

if (!port) return { error: 'port agent returned nothing' }

const REFUTE = {
  type: 'object',
  properties: {
    verdict: { type: 'string', enum: ['sound', 'needs_revision'] },
    blocking: { type: 'array', items: { type: 'object', properties: { issue: { type: 'string' }, why: { type: 'string' }, evidence: { type: 'string' }, fix: { type: 'string' } }, required: ['issue', 'why', 'evidence', 'fix'] } },
    nonblocking: { type: 'array', items: { type: 'string' } },
  },
  required: ['verdict', 'blocking', 'nonblocking'],
}

const LENSES = [
  { key: 'refute-invariants', lens: `Lens: Pystachy's maintainer. Check the ported prototype (${T}, diff in ${S}/stage3/ffi-prototype.patch) against the invariants: the CPython-or-compile-error contract (does every FFI program run under CPython through the twins with the same output; is every divergence either checked, rejected with file:line, or a listed deviation), the fixed point, the Python-free build (do any new build steps need Python or Python.h), irsame/pay-for-use against base, the Wasm GC rule for runtime.py, make lint, and whether each stage is a reviewable PR. Re-run anything you doubt.` },
  { key: 'refute-interop', lens: `Lens: a veteran of bidirectional runtime interop (pythonnet, PyO3, nanobind, PythonCall.jl). Attack the prototype (${T}) for: GC roots of Pystachy objects reachable only from CPython, stack-bottom handling on nested and re-entrant calls, reference ownership and the deferred release of Python references, exception firewalls in both directions, the GIL and free-threaded builds, threads other than the owner, signals and Ctrl-C, interpreter shutdown order, output interleaving between Pystachy's stdout and sys.stdout, two Pystachy extension modules in one process, pickling and multiprocessing. Write and run small adversarial programs in ${S}/stage3/refute-interop.` },
  { key: 'refute-recommendation', lens: `Lens: the recommendation itself. Given the evidence, is the JIT/AOT answer per direction right (Pystachy->C both; Pystachy->CPython both; CPython->Pystachy AOT only, with a compile-on-import cache later)? Are the dismissed alternatives dismissed for the right reasons and with current facts: an in-process ORC JIT inside CPython (ctypes+libLLVM, llvmlite), typed-IR §7.4's third lowering, HPy / PyNI / PEP 809, Python.h-based or version-specific glue, a shared libpystachy runtime, header importers? Re-verify the load-bearing external facts that could have changed: CPython 3.15.0's release, PEP 803 (abi3t) and PEP 793 status, the support window (which versions are supported today), llvmlite's latest release. Load WebSearch/WebFetch with ToolSearch ("select:WebSearch,WebFetch"). Also check fit with the new open issue #108 (use mcp__github__issue_read, owner den-run-ai, repo pystachy, after loading it with ToolSearch "select:mcp__github__issue_read") and with main's changes since cbab8c3.` },
]

phase('Refute')
const draft = `${S}/stage2out/synthesis_draft.json`
const refutes = (await parallel(LENSES.map(l => () =>
  agent(`${CONTEXT}\n\n${l.lens}\n\nThe draft recommendation is ${draft}; the earlier refutation is ${S}/stage2out/refutation.json. The port agent's report on the ported, finished prototype:\n${JSON.stringify(port, null, 1)}\n\nTry hard to REFUTE the recommendation and the prototype that backs it. Only call something blocking if it is a real error (it would crash, leak without bound, silently diverge from CPython, break an invariant, or make the recommendation wrong), not a preference. Give evidence: file:line, a command and its output, or a URL.`,
    { label: l.key, phase: 'Refute', schema: REFUTE })
    .then(r => r ? { key: l.key, ...r } : null)))).filter(Boolean)

const blocking = refutes.flatMap(r => r.blocking.map(b => ({ from: r.key, ...b })))
log(`refuters: ${refutes.map(r => `${r.key}=${r.verdict}(${r.blocking.length})`).join(', ')}`)

let fix = null
if (blocking.length) {
  phase('Fix')
  fix = await agent(`${CONTEXT}\n\nThe ported prototype is in ${T} (branch ffi, base branch base). The port report:\n${JSON.stringify(port, null, 1)}\n\nRefuters found these blocking issues:\n${JSON.stringify(blocking, null, 1)}\n\nVerify each one yourself. Fix the real ones in ${T} (commit on branch ffi), and reject the rest with evidence. Then re-run the full verification the port agent ran (make fixed point, runtime.py IR identical, check_runtime, rtabi, tests/run.sh, make irsame REF=base, make check-ir, make lint, the FFI probes on every CPython version, GC stress, UBSan), rewrite ${S}/stage3/ffi-prototype.patch, and report in the same form. In nonblocking, list each refuter issue with fixed/documented/rejected.`,
    { label: 'fix-and-reverify', phase: 'Fix', schema: PORT })
}

phase('Write')
const FINAL = {
  type: 'object',
  properties: {
    recommendation_md: { type: 'string', description: 'Absolute path of the markdown file written' },
    headline: { type: 'string', description: 'The recommendation in 2-3 sentences' },
    jit_aot: {
      type: 'object',
      properties: { pystachy_to_c: { type: 'string' }, pystachy_to_cpython: { type: 'string' }, cpython_to_pystachy: { type: 'string' } },
      required: ['pystachy_to_c', 'pystachy_to_cpython', 'cpython_to_pystachy'],
    },
    verification_summary: { type: 'string' },
    open_decisions: { type: 'array', items: { type: 'string' } },
    caveats: { type: 'array', items: { type: 'string' } },
  },
  required: ['recommendation_md', 'headline', 'jit_aot', 'verification_summary', 'open_decisions', 'caveats'],
}

const final = await agent(`${CONTEXT}\n\nWrite the FINAL recommendation for the user, as a markdown document at ${S}/stage3/RECOMMENDATION.md. It answers the question asked ("best FFI mechanism ... minimal impact ... CPython bidirectionally ... JIT or AOT or both"). Lead with the answer: one table with the three directions (Pystachy calls C; Pystachy calls CPython; CPython calls Pystachy), the mechanism, and JIT / AOT / both, each with the one-line reason. Then, for each direction: what the user writes (real code that runs under CPython too) and the command; how it keeps the contract (the CPython twin); the boundary rules (types, lifetimes, exceptions, threads/GIL). Then: the CPython ABI targets and why; why not the alternatives (in-process JIT inside CPython, typed-IR §7.4 lowering now, HPy/PyNI/PEP 809, Python.h glue, a shared runtime library, header importers) with the measured or cited reason; the staged plan (S0-S6) with what each stage changes (files, lines) and its acceptance test; the deviations to document; the open decisions for the maintainer; and the evidence: what the prototype on current main proves, with the exact verification results and measurements (only claims backed by the logs; say what was not run). Mention issue #4 §4 and #108 where they bear on it. Write plainly for the repo's maintainer, who knows the codebase: concrete, no filler, file:line references against current main. Aim for something one can read in 10-15 minutes.\n\nSources: the draft ${draft}; the judges ${S}/stage2out/judgments.json; the verifications ${S}/stage2out/verifications.json; the earlier refutation ${S}/stage2out/refutation.json; stage 1 in ${S}/stage1/.\n\nPORT REPORT:\n${JSON.stringify(port, null, 1)}\n\nREFUTATIONS:\n${JSON.stringify(refutes, null, 1)}\n\nFIX REPORT (null if no fix round ran):\n${JSON.stringify(fix, null, 1)}\n\nNever state a refuted claim, and never claim a check passed unless a report shows it passed on the current tree. If a refuter's blocking issue was not fixed, say so and say what it means for the recommendation.`,
  { label: 'write-final', phase: 'Write', schema: FINAL })

return { final, port, refutes, fix }
