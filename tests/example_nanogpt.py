# nanoGPT forward: independent PyTorch float64 reference, batching, causality,
# tied output embeddings, last-position projection and strict offline input.
# Reference: karpathy/nanoGPT 3adf61e154c3fe3fca428ad6bc3818b27a3b8291,
# PyTorch 2.14.1+cpu; model.double().eval(), dropout=0, the weights below.
import math
import os
import tempfile

from driver import read_input
from model import GPT, GPTConfig, cross_entropy, forward, load_weights, parameter_shapes
from ndarray import NDArray, zeros


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


def close(actual: list[float], expected: list[float]) -> None:
    assert len(actual) == len(expected)
    for i in range(len(actual)):
        assert math.isfinite(actual[i])
        assert abs(actual[i] - expected[i]) < 1e-12


expected_bias = [
    0.10167514979424222, 0.043448470081925754, -0.10421385677297293, 0.10302714979424223, 0.04480047008192577,
    -0.14638308346573717, 0.2578374079403264, 0.017587652921767793, -0.14503108346573715, 0.2591894079403264,
    -0.15749140035827644, 0.2353135436364973, 0.10121648809409543, -0.15613940035827645, 0.2366655436364973,
    -0.10826823060200524, 0.18278176214177402, 0.15753390833572606, -0.10691623060200522, 0.18413376214177402,
    -0.12375240204002533, 0.2537685515500684, 0.011688915120532384, -0.12240040204002534, 0.2551205515500684,
    -0.11752198345374754, 0.1900365178501404, 0.155711650881844, -0.11616998345374752, 0.19138851785014044,
]
expected_no_bias = [
    0.1975990275375958, -0.21489620458431644, -0.07743333317834622, 0.19759902753759584, -0.2148962045843164,
    -0.16059247636028273, 0.2683911382427612, 0.0356990212694752, -0.16059247636028273, 0.2683911382427612,
    -0.1592220270627958, 0.18900829484298592, 0.1881383157201292, -0.1592220270627958, 0.18900829484298595,
    0.07792646215993447, -0.1384281997868032, 0.19129238429035908, 0.07792646215993448, -0.13842819978680318,
    -0.03591544300823854, 0.19190088463263158, 0.007263614331467265, -0.03591544300823855, 0.19190088463263158,
    0.059920444082946986, -0.12265638951012824, 0.20823428009127332, 0.059920444082947, -0.12265638951012822,
]
tokens = [0, 1, 1, 2, 0, 3]
targets = [1, 2, -1, 3, 4, -1]
for bias in [True, False]:
    model = make_model(bias)
    expected = expected_bias if bias else expected_no_bias
    loss = 1.6187276891438147 if bias else 1.6257527289152982
    logits = forward(model, tokens, 2, 3)
    assert logits.shape == [2, 3, 5]
    close(logits.values(), expected)
    assert abs(cross_entropy(logits, targets) - loss) < 1e-12
    assert math.isnan(cross_entropy(logits, [-1] * 6))
    last = forward(model, tokens, 2, 3, True)
    assert last.shape == [2, 1, 5]
    close(last.values(), expected[10:15] + expected[25:30])
    # Changing later tokens cannot alter earlier outputs or another batch item.
    changed = forward(model, [0, 1, 4, 4, 4, 4], 2, 3)
    close(changed.values()[:10], expected[:10])
    short = forward(model, [0, 1], 1, 2)
    close(short.values(), expected[:10])
    assert "lm_head.weight" not in model.parameters
    print("upstream logits, loss, last position and causal prefix", bias)

# The final projection observes the same weight object, rather than a stale copy.
model = make_model(False)
before = forward(model, [1], 1, 1)
weight = model.parameters["transformer.wte.weight"]
weight.data[0] += 0.5
after = forward(model, [1], 1, 1)
assert abs(after.values()[0] - before.values()[0]) > 1e-6
close(after.values()[1:], before.values()[1:])
print("output projection observes tied embedding updates")

weights = """PYSTACHY_NANOGPT_V1
0 1 2 2 3 0
3
transformer.wte.weight 2 3 2
0.1 0.2 0.3 0.4 0.5 0.6
transformer.wpe.weight 2 2 2
0.0 0.1
0.2 0.3
transformer.ln_f.weight 1 2
1.0 1.0
"""
directory = tempfile.mkdtemp()
weight_path = directory + "/model.weights"
input_path = directory + "/case.input"
try:
    with open(weight_path, "w") as file:
        file.write(weights)
    with open(input_path, "w") as file:
        file.write("2 2\n0 1 2 0\n1 -1 0 2\n")
    loaded = load_weights(weight_path)
    inputs = read_input(input_path)
    assert inputs.batch == 2 and inputs.length == 2
    assert inputs.tokens == [0, 1, 2, 0] and inputs.targets == [1, -1, 0, 2]
    assert loaded.parameters["transformer.wpe.weight"].values() == [0.0, 0.1, 0.2, 0.3]
    assert forward(loaded, inputs.tokens, inputs.batch, inputs.length).shape == [2, 2, 3]
    print("offline weights and input round trip")
    broken_weights = [
        weights.replace("PYSTACHY_NANOGPT_V1", "UNKNOWN"),
        weights.replace("0 1 2 2 3 0", "0 1 2 2 3 2"),
        weights.replace("\n3\n", "\n2\n"),
        weights.replace("transformer.wte.weight 2 3 2", "transformer.wte.weight 2 3 3"),
        weights.replace("transformer.wpe.weight 2 2 2", "transformer.wte.weight 2 3 2"),
        weights.replace("0.1 0.2 0.3 0.4 0.5 0.6", "nan 0.2 0.3 0.4 0.5 0.6"),
        weights.replace("1.0 1.0\n", ""),
        weights.replace("0.1 0.2 0.3 0.4 0.5 0.6", "0.1 0.2 0.3 0.4 0.5 0.6 0.7"),
        weights + "extra\n",
    ]
    for text in broken_weights:
        with open(weight_path, "w") as file:
            file.write(text)
        try:
            load_weights(weight_path)
            assert False
        except ValueError as error:
            print("weights rejected:", error)
    for text in ["2\n0 1\n1 2\n", "0 2\n\n\n", "1 2\n0\n1 2\n", "1 2\n0 1\n1\n", "1 1\n0\n1\nextra\n"]:
        with open(input_path, "w") as file:
            file.write(text)
        try:
            read_input(input_path)
            assert False
        except ValueError as error:
            print("input rejected:", error)
finally:
    os.remove(weight_path)
    os.remove(input_path)
    os.rmdir(directory)

for kind in range(5):
    try:
        if kind == 0:
            forward(model, [-1], 1, 1)
        elif kind == 1:
            forward(model, [0, 1], 1, 1)
        elif kind == 2:
            forward(model, [0, 1, 2, 3], 1, 4)
        elif kind == 3:
            cross_entropy(before, [5])
        else:
            GPTConfig(1, 3, 4, 3, 5, False)
        assert False
    except ValueError as error:
        print("model rejected:", error)
