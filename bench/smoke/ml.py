"""Small ML algorithms, not full model training or an ndarray/BLAS benchmark.

Value is adapted from bench/microgpt/microgpt.py: Copyright (c) 2026 Andrej
Karpathy, MIT; see ../microgpt/LICENSE. Only add, multiply and reverse-mode
traversal are retained. The deterministic DAG and dense/softmax driver are new.
"""
from __future__ import annotations

import math
import sys
import time


class Value:
    __slots__ = ("data", "grad", "children", "local_grads")

    def __init__(self, data: float, children: list[Value] | None = None,
                 local_grads: tuple[float, ...] = ()) -> None:
        self.data = data
        self.grad = 0.0
        self.children = children if children is not None else []
        self.local_grads = local_grads

    def __add__(self, other: Value) -> Value:
        return Value(self.data + other.data, [self, other], (1.0, 1.0))

    def __mul__(self, other: Value) -> Value:
        return Value(self.data * other.data, [self, other], (other.data, self.data))

    def backward(self) -> None:
        topo: list[Value] = []
        visited: set[Value] = set()

        def visit(node: Value) -> None:
            if node not in visited:
                visited.add(node)
                for child in node.children:
                    visit(child)
                topo.append(node)

        visit(self)
        self.grad = 1.0
        for node in reversed(topo):
            for child, local in zip(node.children, node.local_grads):
                child.grad += local * node.grad


def graph(x: Value, w: Value) -> Value:
    product = x * w
    shared = product + x
    return shared * shared + product


def autograd(iterations: int) -> int:
    checksum = 0
    for i in range(iterations):
        x = Value(float(i % 31 + 1) / 16.0)
        w = Value(float(i % 7 + 1) / 8.0)
        loss = graph(x, w)
        loss.backward()
        # Binary fractions make this checksum exact, including both leaf gradients.
        checksum += int((loss.data + x.grad + w.grad) * 65536.0)
    return checksum


def project_softmax(x: list[float], weights: list[float], width: int) -> list[float]:
    logits: list[float] = []
    for row in range(width):
        value = 0.0
        for column in range(width):
            value += weights[row * width + column] * x[column]
        logits.append(value)
    peak = max(logits)
    probabilities = [math.exp(value - peak) for value in logits]
    total = sum(probabilities)
    return [value / total for value in probabilities]


def numeric(iterations: int) -> int:
    width = 24
    weights = [float(i % 13 - 6) / 32.0 for i in range(width * width)]
    checksum = 0
    for i in range(iterations):
        x = [float((i + j) % 17 - 8) / 8.0 for j in range(width)]
        probabilities = project_softmax(x, weights, width)
        weighted = 0.0
        for j in range(width):
            weighted += float(j + 1) * probabilities[j]
        checksum += int(weighted * 1000000.0)
    return checksum


def check() -> None:
    x, w = Value(2.0), Value(3.0)
    loss = graph(x, w)
    loss.backward()
    # f=(x*w+x)^2+x*w, df/dx=2*(x*w+x)*(w+1)+w, df/dw=2*(x*w+x)*x+x.
    assert loss.data == 70.0 and x.grad == 67.0 and w.grad == 34.0
    probabilities = project_softmax([0.0, math.log(3.0)], [1.0, 0.0, 0.0, 1.0], 2)
    assert abs(probabilities[0] - 0.25) < 1e-12
    assert abs(probabilities[1] - 0.75) < 1e-12


def main() -> None:
    mode, iterations = sys.argv[1], int(sys.argv[2])
    if iterations < 1 or mode not in ("autograd", "numeric"):
        raise ValueError("expected autograd|numeric and a positive iteration count")
    check()
    start = time.perf_counter()
    checksum = autograd(iterations) if mode == "autograd" else numeric(iterations)
    elapsed = time.perf_counter() - start
    print(mode, checksum)
    print("seconds", elapsed, file=sys.stderr)


if __name__ == "__main__":
    main()
