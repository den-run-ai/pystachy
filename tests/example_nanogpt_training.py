# Native regression for analytic gradients, ignored targets and AdamW grouping.
# tools/bench_nanogpt_native.py separately compares every gradient/moment with PyTorch.
import math

from model import GPT, GPTConfig, cross_entropy, forward, parameter_shapes
from ndarray import NDArray, zeros
from training import AdamW, cross_entropy_backward, loss_and_grad


def make_model(bias: bool) -> GPT:
    config = GPTConfig(1, 2, 4, 3, 5, bias)
    parameters: dict[str, NDArray] = {}
    for name, shape in parameter_shapes(config).items():
        value = zeros(shape)
        for i in range(value.size):
            value.data[i] = float((i * 7 + len(name)) % 17 - 8) * 0.013
        if name.endswith(".weight") and len(shape) == 1:
            value.data = [1.0] * shape[0]
        parameters[name] = value
    return GPT(config, parameters)


def directional_check(bias: bool) -> None:
    model = make_model(bias)
    tokens = [0, 1, 1, 2, 0, 3]
    targets = [1, 2, -1, 3, 4, -1]
    result = loss_and_grad(model, tokens, targets, 2, 3)
    assert len(result.gradients) == len(model.parameters)
    assert "lm_head.weight" not in result.gradients
    assert abs(result.loss - cross_entropy(forward(model, tokens, 2, 3), targets)) < 1e-14
    # Independent finite differences perturb every parameter, including both uses
    # of the tied token embedding. Several directions catch sign/index mistakes.
    epsilon = 1e-5
    for direction in range(3):
        plus: dict[str, NDArray] = {}
        minus: dict[str, NDArray] = {}
        predicted = 0.0
        offset = 0
        for name, parameter in model.parameters.items():
            high = parameter.copy()
            low = parameter.copy()
            for i in range(parameter.size):
                delta = float(((offset + i) * (direction * 2 + 3) + 5) % 13 - 6) / 13.0
                high.data[i] += epsilon * delta
                low.data[i] -= epsilon * delta
                predicted += result.gradients[name].data[i] * delta
            plus[name] = high
            minus[name] = low
            offset += parameter.size
        high_loss = cross_entropy(forward(GPT(model.config, plus), tokens, 2, 3), targets)
        low_loss = cross_entropy(forward(GPT(model.config, minus), tokens, 2, 3), targets)
        measured = (high_loss - low_loss) / (2.0 * epsilon)
        assert abs(measured - predicted) < 2e-7
    ignored = loss_and_grad(model, tokens, [-1] * 6, 2, 3)
    assert math.isnan(ignored.loss)
    for gradient in ignored.gradients.values():
        for value in gradient.data:
            assert value == 0.0
    print("gradient directions and ignored targets", bias)


directional_check(True)
directional_check(False)

model = make_model(True)
optimizer = AdamW(model, lr=0.01, beta1=0.8, beta2=0.9, eps=1e-6, weight_decay=0.2)
gradients: dict[str, NDArray] = {}
before: dict[str, NDArray] = {}
for name, parameter in model.parameters.items():
    before[name] = parameter.copy()
    gradients[name] = zeros(parameter.shape)
optimizer.step(gradients)
assert optimizer.step_index == 1
for name, parameter in model.parameters.items():
    factor = 0.998 if parameter.ndim >= 2 else 1.0
    for i in range(parameter.size):
        assert abs(parameter.data[i] - before[name].data[i] * factor) < 1e-15
        assert optimizer.first_moment[name].data[i] == 0.0
        assert optimizer.second_moment[name].data[i] == 0.0
print("AdamW decays matrices and embeddings, not vectors")

# Shape validation is transactional: neither parameters nor the step advance.
gradients["transformer.wte.weight"] = zeros([1])
try:
    optimizer.step(gradients)
    assert False
except ValueError:
    assert optimizer.step_index == 1
print("AdamW rejects malformed gradients before updates")

model = make_model(False)
weight = model.parameters["transformer.wte.weight"]
model.parameters["transformer.wte.weight"] = NDArray([0.0] + weight.data, weight.shape, weight.strides, 1)
try:
    loss_and_grad(model, [0], [1], 1, 1)
    assert False
except ValueError:
    print("training rejects nonwhole parameter views")
try:
    AdamW(model)
    assert False
except ValueError:
    print("AdamW rejects nonwhole parameter views")

logits = zeros([1, 3])
try:
    cross_entropy_backward(logits, [3])
    assert False
except ValueError:
    print("cross entropy rejects invalid target")

# PyTorch permits eps=0, and gives NaN for zero/zero rather than raising.
model = make_model(False)
optimizer = AdamW(model, eps=0.0)
gradients = {}
for name, parameter in model.parameters.items():
    gradients[name] = zeros(parameter.shape)
optimizer.step(gradients)
assert math.isnan(model.parameters["transformer.wte.weight"].data[0])
print("AdamW eps zero follows IEEE division")
