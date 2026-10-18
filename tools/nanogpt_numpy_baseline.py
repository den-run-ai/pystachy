"""CPython + NumPy baseline for the nanoGPT example's inference timings.

Runs a NumPy float64 port of the same dropout-free forward pass on a fixture that
tools/check_nanogpt.py exported, checks every logit and the loss against that
fixture's PyTorch reference, and times full logits + loss and last-position
logits as the checker's runners do (warmups, then repeats, within one process).
With --upstream-model it also times upstream PyTorch on the same weights in the
same process, paired with NumPy. Needs NumPy, and SciPy for GELU's exact erf;
every common BLAS thread variable is set to one thread before either is loaded.

    python3 tools/check_nanogpt.py --upstream-model /path/to/nanoGPT/model.py \\
      --torch-python /path/to/python --benchmark --export-only build/nanogpt-fixtures
    /path/to/python tools/nanogpt_numpy_baseline.py --fixtures build/nanogpt-fixtures \\
      --upstream-model /path/to/nanoGPT/model.py --json build/nanogpt-numpy.json
"""

import argparse
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import time

import check_nanogpt as checker

for _name in checker.THREAD_ENV:
    os.environ[_name] = "1"


def read_weights(path, np):
    """PYSTACHY_NANOGPT_V1 text weights: configuration and C-order float64 arrays."""
    with Path(path).open() as reader:
        if reader.readline().strip() != "PYSTACHY_NANOGPT_V1":
            raise ValueError("unsupported weights format")
        n_layer, n_head, n_embd, block_size, vocab_size, bias = (int(v) for v in reader.readline().split())
        parameters = {}
        for _ in range(int(reader.readline())):
            header = reader.readline().split()
            shape = [int(value) for value in header[2:]]
            values = []
            while len(values) < math.prod(shape):
                values.extend(float(value) for value in reader.readline().split())
            parameters[header[0]] = np.array(values, dtype=np.float64).reshape(shape)
    config = {"n_layer": n_layer, "n_head": n_head, "n_embd": n_embd,
              "block_size": block_size, "vocab_size": vocab_size, "bias": bias == 1}
    return config, parameters


def read_input(path, np):
    with Path(path).open() as reader:
        batch, length = (int(value) for value in reader.readline().split())
        tokens = np.array([int(value) for value in reader.readline().split()]).reshape(batch, length)
        targets = np.array([int(value) for value in reader.readline().split()]).reshape(batch, length)
    return tokens, targets


def numpy_model(config, parameters, np, erf):
    """Return forward(tokens, targets=None) -> (logits, loss), upstream's math in float64."""
    width = config["n_embd"]
    heads = config["n_head"]
    depth = width // heads
    scale = 1.0 / math.sqrt(depth)
    root_two = math.sqrt(2.0)
    wte = parameters["transformer.wte.weight"]
    wpe = parameters["transformer.wpe.weight"]

    def layer_norm(x, prefix):
        mean = x.mean(-1, keepdims=True)
        variance = ((x - mean) ** 2).mean(-1, keepdims=True)
        y = (x - mean) / np.sqrt(variance + 1e-5) * parameters[prefix + ".weight"]
        bias = parameters.get(prefix + ".bias")
        return y if bias is None else y + bias

    def linear(x, prefix):
        y = x @ parameters[prefix + ".weight"].T
        bias = parameters.get(prefix + ".bias")
        return y if bias is None else y + bias

    def forward(tokens, targets=None):
        batch, length = tokens.shape
        x = (wte[tokens] + wpe[:length]).reshape(batch * length, width)
        future = np.triu(np.ones((length, length), dtype=bool), 1)
        for layer in range(config["n_layer"]):
            prefix = f"transformer.h.{layer}."
            qkv = linear(layer_norm(x, prefix + "ln_1"), prefix + "attn.c_attn")
            q, k, v = (qkv[:, i * width:(i + 1) * width].reshape(batch, length, heads, depth).transpose(0, 2, 1, 3)
                       for i in range(3))
            scores = (q @ k.transpose(0, 1, 3, 2)) * scale
            scores[..., future] = -np.inf
            weights = np.exp(scores - scores.max(-1, keepdims=True))
            weights /= weights.sum(-1, keepdims=True)
            attention = (weights @ v).transpose(0, 2, 1, 3).reshape(batch * length, width)
            x = x + linear(attention, prefix + "attn.c_proj")
            hidden = linear(layer_norm(x, prefix + "ln_2"), prefix + "mlp.c_fc")
            hidden = 0.5 * hidden * (1.0 + erf(hidden / root_two))
            x = x + linear(hidden, prefix + "mlp.c_proj")
        x = layer_norm(x, "transformer.ln_f")
        if targets is None:
            return (x.reshape(batch, length, width)[:, -1, :] @ wte.T).reshape(batch, 1, -1), None
        logits = x @ wte.T
        flat = targets.reshape(-1)
        kept = flat != -1
        if not kept.any():
            return logits.reshape(batch, length, -1), math.nan
        shifted = logits[kept] - logits[kept].max(-1, keepdims=True)
        losses = np.log(np.exp(shifted).sum(-1)) - shifted[np.arange(int(kept.sum())), flat[kept]]
        return logits.reshape(batch, length, -1), float(losses.mean())

    return forward


def timed(function, warmups, repeats):
    samples = []
    for iteration in range(warmups + repeats):
        start = time.perf_counter()
        function()
        elapsed = time.perf_counter() - start
        if iteration >= warmups:
            samples.append(elapsed)
    return samples


def summary(samples):
    ordered = sorted(samples)
    return {"median_ms": statistics.median(ordered) * 1e3, "p10_ms": ordered[len(ordered) // 10] * 1e3,
            "p90_ms": ordered[(9 * len(ordered)) // 10] * 1e3}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fixtures", type=Path, required=True, help="directory exported by check_nanogpt.py")
    parser.add_argument("--case", default="benchmark")
    parser.add_argument("--upstream-model", type=Path, help="pinned upstream model.py: also time PyTorch, paired")
    parser.add_argument("--warmups", type=int, default=20)
    parser.add_argument("--repeats", type=int, default=300)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    if args.warmups < 0 or args.repeats < 1:
        parser.error("warmups >= 0 and repeats >= 1 are required")
    try:
        import numpy as np
        from scipy.special import erf
    except ImportError as error:
        parser.error(f"NumPy and SciPy (GELU's exact erf) are required: {error}")
    reference_path = args.fixtures / f"{args.case}.json"
    weights = args.fixtures / f"{args.case}.weights"
    inputs = args.fixtures / f"{args.case}.input"
    reference = json.loads(reference_path.read_text())
    if checker.digest(weights) != reference["weight_sha256"] or checker.digest(inputs) != reference["input_sha256"]:
        raise SystemExit("fixture weights or inputs differ from their reference")
    start = time.perf_counter()
    config, parameters = read_weights(weights, np)
    load_seconds = time.perf_counter() - start
    tokens, targets = read_input(inputs, np)
    forward = numpy_model(config, parameters, np, erf)

    full_logits, loss = forward(tokens, targets)
    last_logits, _ = forward(tokens)
    expected = {"full": {"logits": reference["checks"]["full"]["logits"], "loss": reference["checks"]["full"]["loss"]},
                "last": {"logits": reference["checks"]["last"]["logits"]}}
    actual = {"full": {"logits": full_logits.reshape(-1).tolist(), "loss": loss},
              "last": {"logits": last_logits.reshape(-1).tolist()}}
    report = {"case": reference["case"], "platform": platform.platform(), "python": sys.version,
              "thread_environment": {name: os.environ[name] for name in checker.THREAD_ENV},
              "warmups": args.warmups, "repeats": args.repeats,
              "numpy": {"version": np.__version__, "load_seconds": load_seconds,
                        "comparison": checker.compare(expected, actual)}}
    report["numpy"]["full_seconds"] = timed(lambda: forward(tokens, targets), args.warmups, args.repeats)
    report["numpy"]["last_seconds"] = timed(lambda: forward(tokens), args.warmups, args.repeats)
    if args.upstream_model:
        if checker.digest(args.upstream_model) != checker.UPSTREAM_SHA256:
            raise SystemExit("upstream model.py differs from the pinned nanoGPT source")
        import torch

        torch.set_num_threads(1)
        torch.set_num_interop_threads(1)
        sys.path.insert(0, str(args.upstream_model.resolve().parent))
        from model import GPT, GPTConfig

        model = GPT(GPTConfig(dropout=0.0, **config)).double().eval()
        state = {name: torch.from_numpy(value) for name, value in parameters.items()}
        state["lm_head.weight"] = state["transformer.wte.weight"]
        loaded = model.load_state_dict(state, strict=False)
        if loaded.unexpected_keys or any(not key.endswith(".attn.bias") for key in loaded.missing_keys):
            raise SystemExit(f"upstream parameters differ: {loaded}")
        x = torch.from_numpy(tokens)
        y = torch.from_numpy(targets)
        with torch.inference_mode():
            torch_logits, torch_loss = model(x, y)
            torch_last, _ = model(x)
            report["torch"] = {"version": torch.__version__, "threads": torch.get_num_threads(),
                               "comparison": checker.compare(expected, {
                                   "full": {"logits": torch_logits.reshape(-1).tolist(), "loss": torch_loss.item()},
                                   "last": {"logits": torch_last.reshape(-1).tolist()}}),
                               "full_seconds": timed(lambda: model(x, y), args.warmups, args.repeats),
                               "last_seconds": timed(lambda: model(x), args.warmups, args.repeats)}
    for implementation in ("numpy", "torch"):
        if implementation in report:
            row = report[implementation]
            row["full"] = summary(row["full_seconds"])
            row["last"] = summary(row["last_seconds"])
            print(f"{implementation} {row['version']}: full {row['full']['median_ms']:.3f} ms, "
                  f"last {row['last']['median_ms']:.3f} ms (medians of {args.repeats}); "
                  f"max |error| vs reference {row['comparison']['max_absolute_error']:.2e}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
