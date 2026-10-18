"""Shared CLI for the scalar and optional BLAS nanoGPT inference examples."""
import sys

from model import cross_entropy, forward_with_backend, load_weights


class InputBatch:
    def __init__(self, batch: int, length: int, tokens: list[int], targets: list[int]) -> None:
        self.batch = batch
        self.length = length
        self.tokens = tokens
        self.targets = targets


def read_input(path: str) -> InputBatch:
    """Read the exporter's three lines: B T, flattened tokens, flattened targets."""
    with open(path) as reader:
        dimensions = [int(value) for value in reader.readline().split()]
        if len(dimensions) != 2 or dimensions[0] < 1 or dimensions[1] < 1:
            raise ValueError("input header must contain positive batch and sequence lengths")
        tokens = [int(value) for value in reader.readline().split()]
        targets = [int(value) for value in reader.readline().split()]
        count = dimensions[0] * dimensions[1]
        if len(tokens) != count or len(targets) != count:
            raise ValueError("input token and target counts must equal batch times sequence length")
        if reader.read().strip() != "":
            raise ValueError("unexpected trailing input content")
    return InputBatch(dimensions[0], dimensions[1], tokens, targets)


def main(matmul_fn, linear_fn=None) -> None:
    """Default: last-position logits. --loss evaluates only the returned positions.

    linear_fn, when given, computes the model's biased projections (see model.py).
    """
    usage = "usage: run.py WEIGHTS INPUT [--last|--full] [--loss]"
    if len(sys.argv) == 2 and sys.argv[1] == "--help":
        print(usage)
        return
    if len(sys.argv) < 3:
        print(usage)
        sys.exit(2)
    last_only = True
    evaluate_loss = False
    for option in sys.argv[3:]:
        if option == "--last":
            last_only = True
        elif option == "--full":
            last_only = False
        elif option == "--loss":
            evaluate_loss = True
        else:
            raise ValueError("unknown option: " + option)
    model = load_weights(sys.argv[1])
    inputs = read_input(sys.argv[2])
    logits = forward_with_backend(model, inputs.tokens, inputs.batch, inputs.length, matmul_fn, last_only, linear_fn)
    print("shape", logits.shape)
    print("logits", logits.values())
    if evaluate_loss:
        targets = inputs.targets
        if last_only:
            targets = [targets[(batch + 1) * inputs.length - 1] for batch in range(inputs.batch)]
        print("loss", cross_entropy(logits, targets))
