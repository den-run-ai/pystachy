# Byte BPE: train, encode and decode in native Python

This example compiles an educational byte-pair tokenizer with Pystachy. It learns a
vocabulary from UTF-8 text, encodes text as integer token IDs, and decodes those IDs
back to the original text. The vocabulary starts with all 256 byte values, so unseen
Unicode text remains encodable. Training, encoding and decoding run natively.

The implementation is Shantanu Jain's
[pyperformance 1.14.0 byte-BPE benchmark](https://github.com/python/pyperformance/blob/2ab96f98f98274d07ebfdfd66e4f021723179706/pyperformance/data-files/benchmarks/bm_bpe_tokeniser/run_benchmark.py),
derived from OpenAI's educational tiktoken code. It is a useful companion to
[Sebastian Raschka's tokenizer teaching examples](https://github.com/rasbt/LLMs-from-scratch/tree/main/ch02/05_bpe-from-scratch).
It is not a port of Raschka's own implementation or a performance comparison with
production Rust tiktoken. This example does not load GPT-2/tiktoken vocabularies,
implement special tokens, or persist a model between processes.

## Try it

From the repository root, after [building Pystachy](../../docs/install.md#build-from-source):

```sh
PYSTACHY_PATH=bench/pyperformance ./pystachy run examples/byte_bpe/demo.py \
  bench/pyperformance/data/frankenstein_intro.txt 1024 'Hello, Sebastian! 日本語 🦉'

PYSTACHY_PATH=bench/pyperformance ./pystachy build examples/byte_bpe/demo.py -o build/byte-bpe
./build/byte-bpe bench/pyperformance/data/frankenstein_intro.txt 1024 'Hello, Sebastian! 日本語 🦉'

PYTHONPATH=bench/pyperformance python3 examples/byte_bpe/demo.py \
  bench/pyperformance/data/frankenstein_intro.txt 1024 'Hello, Sebastian! 日本語 🦉'
```

Each invocation trains once and prints the token IDs and an exact text round trip.
Omit the final text argument to exercise Japanese, an emoji, a tab and a newline.
The executable needs its corpus file at run time. Vocabulary size must be at least
256; requesting more merges than the corpus permits raises the upstream `ValueError`.
An empty corpus is valid at size 256. Inputs are never stripped or normalized.

For repeated queries in one process, retain the tokenizer object:

```python
from bpe_tokeniser import BPE_PATTERN, SimpleBytePairEncoding

tokenizer = SimpleBytePairEncoding.train("banana bandana banana", 260, BPE_PATTERN)
tokens = tokenizer.encode("Unseen 日本語 and 🦉 remain encodable.\n")
assert tokenizer.decode(tokens) == "Unseen 日本語 and 🦉 remain encodable.\n"
```

`decode_bytes(ids)` returns the exact concatenated bytes. `decode(ids)` applies
UTF-8 replacement decoding, including for malformed byte sequences. Unknown IDs
raise `KeyError`. The original algorithm recounts pairs for each training merge,
and its uncached encoder repeatedly scans and rebuilds lists; this preserves the
educational implementation's scaling.

## Validate and measure

The benchmark controller needs only CPython, a POSIX host with `wait4`, and a complete
LLVM toolchain. It uses the selected Python interpreter for both CPython baselines.

```sh
# Small, deterministic four-mode correctness check.
python3 examples/byte_bpe/benchmark.py --smoke

# Five interleaved processes per mode, pinned to an available CPU on Linux.
python3 examples/byte_bpe/benchmark.py --processes 5 --cpu 0 --json build/byte-bpe.json

# Optional per-workload memory setting; compare its complete output and timings.
python3 examples/byte_bpe/benchmark.py --processes 5 --cpu 0 --gc-min 8 \
  --json build/byte-bpe-gc8.json

# The existing pyperformance check includes this port; select it alone for a fast check.
python3 tools/bench_pyperformance.py --benchmarks bpe_tokeniser --smoke
tests/run.sh ./pystachy 'jit aot' tests/programs/apps/byte_bpe.py
PYSTACHY_GC_STRESS_PROGRAM=1 tests/run.sh ./pystachy 'jit aot' tests/programs/apps/byte_bpe.py
```

Use an allowed CPU in place of `0`, or omit `--cpu` where affinity is unavailable.
Set `PYSTACHY_LLVM` when LLVM is not discoverable. `--compiler` accepts a command,
including a native compiler's path; hosted compiler measurements have different
startup costs. The controller explicitly disables program caching for its JIT
baseline, uses a private runtime cache, and records runtime preparation separately.

The four modes are **original CPython, adapted CPython, native JIT and AOT**. Original
CPython imports exact kernel source extracted from the hash-pinned pristine file;
only pyperf's runner and file setup are omitted. All four modes use the same stage
driver and input. Original/adapted baselines remain separate because materializing
`zip` changes allocation work.

Every sample must match the original CPython run's complete ordered vocabulary,
token-ID list, decoded bytes and decoded string. The controller builds a fresh AOT
executable, rejects failed commands and malformed timings, bounds subprocess groups,
and marks incomplete or failed reports accordingly. Native correctness cases cover
merge ties, overlaps, unseen Unicode, whitespace, all 256 bytes, malformed UTF-8 and
rejection behavior. They run in the existing differential corpus; the bounded
pyperformance workload runs in its existing job. No extra CI jobs are added.

The full stage workload uses the unchanged **31,206-byte** Frankenstein fixture and
a **1,024-entry** vocabulary. It trains once, encodes 50 times and decodes 200 times
per process. Timings exclude corpus I/O, output comparison and full-state printing.
Each stage's reported time is per operation. Wall time, time outside the stage
timers, build time, peak RSS, sample ranges, toolchain and source hashes are separate.
JIT RSS includes compilation. The report retains `wait4`'s process-family maximum,
which can include the launcher's pre-exec memory high-water mark. On Linux it also
samples the executable's `VmHWM` every approximately 5 ms after its command is
installed; this is the runtime memory comparison for CPython and AOT, excludes
child processes, and can miss a final brief peak. Shared-host timings are advisory;
no timing threshold is a test gate.

The suite's `bench_bpe_tokeniser()` timer instead preserves upstream's composite
training/encoding loop. Its independent untimed correctness pass trains again, so
its process wall time is not an isolated training measurement. See the
[benchmark port notes](../../bench/pyperformance/README.md).

## Port boundary and provenance

The reusable implementation is
[`bench/pyperformance/bpe_tokeniser.py`](../../bench/pyperformance/bpe_tokeniser.py).
Its five kernel changes are marked `# Pystachy port:`: annotate the decoder and
initial ranks, type the pair Counter, materialize `zip` before `enumerate`, and
pass the `bytes.decode` error policy positionally. The compiler/runtime and global
GC defaults are unchanged. JSON file helpers and cached methods are not needed by
this tokenizer; they remain separate library work.

The [upstream manifest](upstream/provenance.json) records pyperformance tag `1.14.0`,
commit `2ab96f98f98274d07ebfdfd66e4f021723179706`, source URLs and SHA-256 hashes.
Its `run_benchmark.py` is stored here as
[`upstream/bpe_tokeniser.py`](upstream/bpe_tokeniser.py); its data file is stored in
[`bench/pyperformance/data`](../../bench/pyperformance/data/frankenstein_intro.txt).
The corpus is Mary Shelley's *Frankenstein* excerpt, unchanged from pyperformance.
The existing [MIT license](../../bench/pyperformance/LICENSE),
[authors](../../bench/pyperformance/AUTHORS) and
[third-party notices](../../THIRD_PARTY_NOTICES) cover the source and its tiktoken origin.
