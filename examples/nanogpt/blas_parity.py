"""Optional BLAS parity of this example, run by make blas-check in each tier.

Compares the BLAS backend, with and without its fused-bias linear(), against
the scalar backend: full and last-position logits, and the loss and every
gradient of a training step, for a small deterministic model with and without
biases. Needs an LP64 libblas.so.3 (../ndarray/README.md); under CPython, also
tools/rt_cpython on the path. The scalar backend is checked against PyTorch by
tools/check_nanogpt.py; BLAS may add in another order, hence the tolerance.
"""
import math

from model import GPT, GPTConfig, forward, forward_with_backend, parameter_shapes
from ndarray import NDArray, zeros
from ndarray_blas import linear, matmul
from training import loss_and_grad, loss_and_grad_with_backend


def make_model(bias: bool) -> GPT:
    config = GPTConfig(2, 2, 8, 6, 7, bias)
    parameters: dict[str, NDArray] = {}
    for name, shape in parameter_shapes(config).items():
        value = zeros(shape)
        for i in range(value.size):
            value.data[i] = float((i * 11 + len(name) * 3) % 23 - 11) * 0.017
        parameters[name] = value
    return GPT(config, parameters)


def close(label: str, actual: list[float], expected: list[float]) -> float:
    # the largest absolute difference, within 1e-12 of each value's magnitude (at least 1)
    assert len(actual) == len(expected), label
    largest = 0.0
    for i in range(len(actual)):
        assert math.isfinite(actual[i]) and math.isfinite(expected[i]), label
        difference = abs(actual[i] - expected[i])
        assert difference <= 1e-12 * max(1.0, abs(expected[i])), label
        largest = max(largest, difference)
    return largest


def main() -> None:
    tokens = [3, 1, 4, 1, 5, 6, 2, 0, 5, 3]
    targets = [1, 4, 1, 5, 6, 2, 0, 5, 3, -1]
    batch = 2
    length = 5
    values = 0
    largest = 0.0
    for bias in [True, False]:
        model = make_model(bias)
        for last_only in [False, True]:
            scalar = forward(model, tokens, batch, length, last_only).values()
            unfused = forward_with_backend(model, tokens, batch, length, matmul, last_only).values()
            fused = forward_with_backend(model, tokens, batch, length, matmul, last_only, linear).values()
            largest = max(largest, close("unfused logits", unfused, scalar))
            largest = max(largest, close("fused logits", fused, scalar))
            values += 2 * len(scalar)
        reference = loss_and_grad(model, tokens, targets, batch, length)
        result = loss_and_grad_with_backend(model, tokens, targets, batch, length, matmul, linear)
        largest = max(largest, close("loss", [result.loss], [reference.loss]))
        largest = max(largest, close("training logits", result.logits.values(), reference.logits.values()))
        values += 1 + result.logits.size
        for name in model.parameters:
            expected = reference.gradients[name].values()
            largest = max(largest, close("gradient of " + name, result.gradients[name].values(), expected))
            values += len(expected)
    print("nanoGPT BLAS parity passed:", values, "values; largest difference", largest)


main()
