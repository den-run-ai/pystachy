# Bounded process jobs and detached workers

This prototype extends the worker lifecycle in [#1091](https://github.com/den-run-ai/pystachy/pull/1091)
and ordinary bootstrap work in [#1111](https://github.com/den-run-ai/pystachy/pull/1111).
The compiler backend is its first consumer; native JSON-repair and byte-BPE batches
demonstrate allocating application jobs. Coordination still runs under CPython.
Every native compiler request starts a fresh process, so this does not assume
that `Gen` can be reset or shared safely.

[Measured results and raw evidence](results/README.md) show a 2.71x scheduling gain
for the same four compiler bitcode partitions, 2.11x JSON-repair batch throughput,
and 2.29x byte-BPE throughput at four workers. These are separate cohorts. They
do not establish a full-bootstrap speedup, an ordinary-O2 quality comparison,
or a physical two-host speedup.

## Implementation boundaries

| Component | Contract |
|---|---|
| `tools/process_workers.py` | Extracted process-group ownership, timeouts, deferred signals, fail-fast admission, TERM/KILL cleanup and `wait4` reaping. Adds CPU, estimated-memory and input reservations, one lazy pending descriptor, bounded captures and output-limit checks. |
| `tools/application_workers.py` | Explicit argv/file jobs using that lifecycle, ordered results and common BLAS/OpenMP thread caps. No shell or object-graph serialization. |
| `bench/compiler_host/backend_workers.py` | Existing LLVM adapter now uses the shared scheduler; optional same-host object cache deduplicates concurrent misses and validates inputs, tools, native dependencies and outputs. |
| `tools/worker_artifacts.py` | Private local POSIX cache: per-key OS lock, validated immutable content, manifest published last. Corruption is a miss; a failed writer cannot replace valid bytes with a misnamed object. |
| `tools/worker_transport.py` | Trusted native jobs over a bounded full-duplex stdio channel, with checked input/output files, exact execution identity, heartbeat leases, EOF cancellation, cache opt-in and idempotent-only transport retries. |
| `bench/compiler_host/self_pipeline.py` | [Atomic executable/IR generation publication](../compiler_host/ARTIFACT_PUBLICATION.md), plus a real next-stage manifest consumer. Legacy file destinations retain their earlier per-file contract. |

`Commands` owns signal handlers and an exclusive process group. Use it in a
dedicated coordinator's main thread, as these CLI adapters do. It is not an
arbitrary-thread `Executor` replacement. Children must not deliberately daemonize
or leave the owned group.

Memory reservations are estimates, not enforced RSS limits. The coordinator
bounds the sum of admitted CPU, memory and input reservations. One descriptor is
prefetched; its declared payload must fit the queued-byte limit. Payload files
remain on disk until a job reads them. The original input store, OS page cache
and already-created producer files are not bounded by this queue. The manifest
itself is limited to 1 MiB and 10,000 descriptors. `queue_s` measures waiting after
descriptor consumption, not time spent in an external submission service.

Application jobs set `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`
and `NUMEXPR_NUM_THREADS` to their CPU reservation. Other nested runtimes must be
configured explicitly. A single coordinator can reserve across its endpoint
requests; independent coordinators do not yet share a host/fleet admission service.

## Run native application batches

Build the JSON-repair consumer with the existing port:

```sh
PYSTACHY_PATH=ports ./pystachy build bench/process_workers/json_batch.py -o build/json-batch
```

An application manifest contains explicit commands and reservations. Paths in
`stdin` and `cwd` are relative to the manifest; use absolute executable paths.

```json
{
  "version": 1,
  "jobs": [
    {
      "key": "repair-0",
      "argv": ["/absolute/build/json-batch", "/absolute/batch.jsonl", "100"],
      "cpu": 1,
      "memory_bytes": 134217728,
      "input_bytes": 16384
    }
  ]
}
```

```sh
python3 tools/application_workers.py jobs.json --report results.json \
  --jobs 4 --cpus 4 --memory-mib 512 --input-mib 64 \
  --queued-input-mib 64 --timeout 60
```

Input reservations are declarations; explicit `stdin` file sizes are checked.
Outputs are spooled rather than piped into an unread parent buffer. The default
combined output ceiling is 1 MiB per job; a violation cancels the group. Polling
can permit a brief disk overshoot before termination. Captures and cleanup reads
remain bounded even for a fast-exiting child with a huge sparse output file.
Results state whether a capture or hash is truncated. A nonzero exit prevents
new admission and cancels/reaps already admitted siblings.

The byte-BPE consumer uses #1107's `bench/pyperformance/bpe_tokeniser.py`; supply
that checkout's `bench/pyperformance` as `PYSTACHY_PATH` and `--import-path`.
It trains a small model once per process and checks complete UTF-8 round trips.
Neither example requires shared managed objects or pickle compatibility.

## Compiler jobs and cache

```sh
python3 bench/compiler_host/backend_workers.py \
  --llvm /path/to/llvm-18/bin --input linked.bc \
  --partitions 4 --jobs 4 --cpu-budget 4 \
  --memory-budget-mib 2048 --worker-memory-mib 512 \
  --input-budget-mib 256 --queued-input-mib 256 \
  --object-cache /private/local/object-cache \
  --work /tmp/backend-run --report /tmp/backend-report.json
```

The cache is explicitly **same-host, Linux, standalone bitcode**. Keys bind the
input and optimizer policy, worker/cache implementation, tool executables,
loader-resolved shared libraries, host/boot identity and the controlled tool
environment. The cache path disables implicit Clang configuration and forwards
only the declared tool environment, including `LD_LIBRARY_PATH` when present.
It is not a general cross-host sysroot cache. ThinLTO indices and imported-body
dependencies are outside this adapter. A changing source invalidates the input;
stable incremental partitions are not implemented.

`ld.lld` is required only when full-LTO partitioning is requested. Ordinary
standalone object jobs use the installed matching Clang/opt tools. Unsupported
LTO setup is rejected rather than silently substituting a different linker.
The serial splitting and final linking remain visible in reports; warm objects
do not skip them.

## Transfer a job to a detached endpoint

The transport accepts Linux ELF executables, either registered under logical tool
names (`@tool:clang`) or included as checked executable inputs (`./program`).
Prepare a spec with explicit argv commands and immutable file inputs:

```json
{
  "version": 1,
  "commands": [["./program", "input.txt", "100"]],
  "inputs": {"program": true, "input.txt": false},
  "outputs": [],
  "cpu": 1,
  "memory_bytes": 134217728,
  "timeout_s": 60,
  "lease_s": 10,
  "idempotent": true,
  "cacheable": false
}
```

```sh
python3 tools/worker_transport.py prepare --spec spec.json \
  --directory input-files --output bundle.json

# Local detached replay; transfer these same three support files to a remote
# endpoint before using an authenticated SSH command in its place.
python3 tools/worker_transport.py relay --bundle bundle.json --result result.json \
  -- python3 -I tools/worker_transport.py serve

# Example endpoint command once the operator has provisioned that host:
python3 tools/worker_transport.py relay --bundle bundle.json --result result.json \
  -- ssh -T worker-host python3 /opt/pystachy-worker/worker_transport.py serve
```

Copy `worker_transport.py`, `process_workers.py` and `worker_artifacts.py` together.
Use `--tool name=/absolute/executable` on both prepare and serve for external tools.
Execution identity checks exact implementation bytes, ELF tools, loader-resolved
native libraries, machine/kernel and CPU-feature fingerprint. Heterogeneous hosts
will conservatively reject the job. Job/result identities bind all commands,
input sizes/modes/hashes, resource settings and the execution identity.

This is an authenticated-channel **trusted-code** protocol, not a sandbox. Tools
that read implicit plugins, configurations, sysroots, external files or nondeterministic
sources must declare the relevant inputs and must not opt into caching otherwise.
`cacheable=true` is an explicit purity/completeness promise, not a compiler proof.
It also requires `idempotent=true`. Caches use private local POSIX storage, not a
network-filesystem locking protocol. No credentials or inherited local environment
are serialized into bundles.

Each file is limited to 16 MiB, total input/output artifact bytes to 32 MiB, and
the wire envelope to 64 MiB. Captured command logs are bounded to 64 KiB, with
full hashes only for fully read bounded output. A checked preflight interval
precedes the work lease; while jobs run, EOF, an expired lease, timeout or signal
cancels the owned process group. Heartbeats use a request nonce. The client sends
EOF when it stops waiting; if the channel disappears without EOF, the lease
expires. Repeated transport attempts default to one and are capped at three,
only for explicitly idempotent jobs. A native command failure is not retried.

## Reproduce the measurements

```sh
python3 bench/process_workers/run.py --kind json --binary build/json-batch \
  --import-path ports --rounds 300 --rows 32 --tasks 8 --samples 3 --cpus 0-3 \
  --work /tmp/json-workers --report /tmp/json-workers.json

python3 bench/process_workers/remote.py \
  --manifest /tmp/json-workers/jobs.json --oracle-report /tmp/json-workers.json \
  --work /tmp/detached-json --report /tmp/detached-json.json

# Obtain linked.bc and compiler/runtime IR witnesses from the existing #1111
# self-build controller, using one frozen source tree for the whole campaign.
python3 bench/process_workers/backend.py --input linked.bc \
  --source-root /frozen/pystachy --compiler-ir raw.ll --runtime-ir runtime.ll \
  --llvm /path/to/llvm-18/bin --samples 3 --work /tmp/backend-workers \
  --report /tmp/backend-workers.json

python3 bench/process_workers/remote.py \
  --backend-run /tmp/backend-workers/sample-2-jobs-4-cold \
  --llvm /path/to/llvm-18/bin --samples 1 \
  --work /tmp/detached-llvm --report /tmp/detached-llvm.json
```

The last pilot replays the exact four LLVM jobs at two detached local endpoints,
checks each object byte-for-byte, then links in stable order and checks the final
compiler bytes. It does not distribute ThinLTO importing or claim network speedup.

Correctness, corruption, resource and lifecycle tests run in the existing Lint
job through `test_process_workers.py`, `test_worker_transport.py` and the existing
`test_compiler_parallel*.py` suites. No timing gates, CI jobs or shards are added.
Timing campaigns remain explicit local experiments. Native subprocess supervision,
numeric threads, general shared-heap threading and native async are separate work.
