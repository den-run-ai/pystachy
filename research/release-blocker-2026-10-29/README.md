# Release blocker performance evidence

Isolated runtime evaluation, 29 October 2026 UTC (28 October Pacific). This branch is raw evidence and must not be merged into main.

The compressed text-only archive includes exact harness/input source, source/build/IR/binary hashes, commands and output checks, all paired timing samples, Callgrind totals/function summaries and SHA256SUMS. Reproducible caches, binaries and full LLVM/Callgrind files are excluded.

Archive SHA256: `e76d1b756f74644567fee9a8d03d1fef5eeaf52f037640fb18cd4ef633c4a665`.

Evaluated runtime source: local `5665d8e9`, published `86cedeec314390005e5a5e21dad01373233d2f6b`, identical tree `491c61ef5894822fbbb5b1cbd52c5a6bfe63565c`. Baselines: main `5b49dcfaf639d943a12cbc00ce9117ba3e7b5fcc` and alpha.3 `f5a09d4223139d7255e31051be97fc509e1ca1fe`.

Program instructions at 300 loops: alpha.3 1,300.339M; main 1,405.530M; runtime fix 1,351.341M. This removes 51.5% of the excess, leaving 3.92%. Shared-host timing ranges overlap. The workload times typed JSONValue decoding within a dynamic-Any program.

Final combined #973 acceptance will be added separately; this archive does not certify that source.
