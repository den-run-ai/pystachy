"""Write byte-BPE probe modules: the pristine upstream kernels and five single reverts.

Usage: python3 make_variants.py MAIN_WORKTREE OUTDIR
Each OUTDIR/<name>/bpe_tokeniser.py is a module for PYSTACHY_PATH/PYTHONPATH.
"""
import hashlib
import sys
from pathlib import Path

main = Path(sys.argv[1])
out = Path(sys.argv[2])
port = (main / "bench/pyperformance/bpe_tokeniser.py").read_text(encoding="utf-8")

REVERTS = {
    "r1_decoder_annotation": (
        "self._decoder: dict[int, bytes] = {token: token_bytes for token_bytes, token in mergeable_ranks.items()}",
        "self._decoder = {token: token_bytes for token_bytes, token in mergeable_ranks.items()}"),
    "r2_errors_keyword": (
        'return self.decode_bytes(tokens).decode("utf-8", "replace")',
        'return self.decode_bytes(tokens).decode("utf-8", errors="replace")'),
    "r3_enumerate_zip": (
        "for i, pair in enumerate(list(zip(parts[:-1], parts[1:]))):",
        "for i, pair in enumerate(zip(parts[:-1], parts[1:])):"),
    "r4_ranks_annotation": (
        "ranks: dict[bytes, int] = {}  # Pystachy port: type the initially empty dictionary",
        "ranks = {}"),
    "r5_untyped_counter": (
        "stats = collections.Counter[tuple[bytes, bytes]]()",
        "stats = collections.Counter()"),
}

(out / "port").mkdir(parents=True)
(out / "port" / "bpe_tokeniser.py").write_text(port, encoding="utf-8")
for name, (old, new) in REVERTS.items():
    if port.count(old) != 1:
        raise SystemExit(f"{name}: expected exactly one occurrence")
    (out / name).mkdir()
    (out / name / "bpe_tokeniser.py").write_text(port.replace(old, new), encoding="utf-8")

# The benchmark controller's own pristine-kernel extraction (hash-checked there).
sys.path.insert(0, str(main / "examples/byte_bpe"))
import benchmark  # noqa: E402

(out / "pristine").mkdir()
text = benchmark.original_module()
(out / "pristine" / "bpe_tokeniser.py").write_text(text, encoding="utf-8")
for p in sorted(out.glob("*/bpe_tokeniser.py")):
    print(hashlib.sha256(p.read_bytes()).hexdigest()[:16], p.parent.name)
