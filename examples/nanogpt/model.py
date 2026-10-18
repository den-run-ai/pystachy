"""Native float64, dropout-free nanoGPT forward pass using the ndarray example.

Architecture and parameter names follow karpathy/nanoGPT model.py at
3adf61e154c3fe3fca428ad6bc3818b27a3b8291 (MIT). Weights are supplied offline;
this module neither imports PyTorch nor downloads checkpoints. Matrix products
use ndarray.matmul by default; forward_with_backend accepts another compatible
function without importing its optional dependencies into the scalar executable.
The backend must return a fresh 2-D NDArray and leave both inputs unchanged;
strided views, including transposed weights, are valid matrix operands.
"""
import math

from ndarray import NDArray, matmul, zeros


class GPTConfig:
    def __init__(self, n_layer: int, n_head: int, n_embd: int,
                 block_size: int, vocab_size: int, bias: bool) -> None:
        if n_layer < 0 or min(n_head, n_embd, block_size, vocab_size) < 1:
            raise ValueError("model dimensions must be positive; layers may be zero")
        if n_embd % n_head != 0:
            raise ValueError("embedding width must be divisible by attention heads")
        self.n_layer = n_layer
        self.n_head = n_head
        self.n_embd = n_embd
        self.block_size = block_size
        self.vocab_size = vocab_size
        self.bias = bias


def parameter_shapes(config: GPTConfig) -> dict[str, list[int]]:
    c = config.n_embd
    shapes = {
        "transformer.wte.weight": [config.vocab_size, c],
        "transformer.wpe.weight": [config.block_size, c],
        "transformer.ln_f.weight": [c],
    }
    if config.bias:
        shapes["transformer.ln_f.bias"] = [c]
    for i in range(config.n_layer):
        prefix = f"transformer.h.{i}."
        shapes[prefix + "ln_1.weight"] = [c]
        shapes[prefix + "attn.c_attn.weight"] = [3 * c, c]
        shapes[prefix + "attn.c_proj.weight"] = [c, c]
        shapes[prefix + "ln_2.weight"] = [c]
        shapes[prefix + "mlp.c_fc.weight"] = [4 * c, c]
        shapes[prefix + "mlp.c_proj.weight"] = [c, 4 * c]
        if config.bias:
            shapes[prefix + "ln_1.bias"] = [c]
            shapes[prefix + "attn.c_attn.bias"] = [3 * c]
            shapes[prefix + "attn.c_proj.bias"] = [c]
            shapes[prefix + "ln_2.bias"] = [c]
            shapes[prefix + "mlp.c_fc.bias"] = [4 * c]
            shapes[prefix + "mlp.c_proj.bias"] = [c]
    return shapes


class GPT:
    def __init__(self, config: GPTConfig, parameters: dict[str, NDArray]) -> None:
        shapes = parameter_shapes(config)
        if len(parameters) != len(shapes):
            raise ValueError("parameter names differ from model configuration")
        for name in shapes:
            if name not in parameters or parameters[name].shape != shapes[name]:
                raise ValueError("missing parameter or wrong shape: " + name)
        self.config = config
        self.parameters = parameters


def _required_line(reader) -> str:
    line = reader.readline()
    if line == "":
        raise ValueError("unexpected end of weights file")
    return line.strip()


def load_weights(path: str) -> GPT:
    """Read PYSTACHY_NANOGPT_V1 text weights; token/output embeddings are tied.

    Header: magic line; six integer config fields in GPTConfig argument order;
    tensor count. Each tensor has `name rank dimensions...` on one line followed
    by its C-order values on one or more lines. lm_head.weight is omitted because
    the output projection uses the exact same array as transformer.wte.weight.
    """
    with open(path) as reader:
        if _required_line(reader) != "PYSTACHY_NANOGPT_V1":
            raise ValueError("unsupported weights format")
        fields = _required_line(reader).split()
        if len(fields) != 6:
            raise ValueError("expected six model configuration fields")
        raw_bias = int(fields[5])
        if raw_bias != 0 and raw_bias != 1:
            raise ValueError("bias flag must be zero or one")
        config = GPTConfig(int(fields[0]), int(fields[1]), int(fields[2]),
                           int(fields[3]), int(fields[4]), raw_bias == 1)
        shapes = parameter_shapes(config)
        count = int(_required_line(reader))
        if count != len(shapes):
            raise ValueError("tensor count differs from model configuration")
        parameters: dict[str, NDArray] = {}
        for _ in range(count):
            header = _required_line(reader).split()
            if len(header) < 3:
                raise ValueError("invalid tensor header")
            name = header[0]
            ndim = int(header[1])
            shape = [int(value) for value in header[2:]]
            if ndim != len(shape) or name not in shapes or shape != shapes[name]:
                raise ValueError("unexpected tensor name or shape: " + name)
            if name in parameters:
                raise ValueError("duplicate tensor: " + name)
            size = 1
            for dimension in shape:
                size *= dimension
            data: list[float] = []
            while len(data) < size:
                values = _required_line(reader).split()
                if not values or len(data) + len(values) > size:
                    raise ValueError("incorrect tensor value count: " + name)
                for value in values:
                    number = float(value)
                    if not math.isfinite(number):
                        raise ValueError("nonfinite tensor value: " + name)
                    data.append(number)
            parameters[name] = NDArray(data, [size], [1], 0).reshape(shape)
        if reader.read().strip() != "":
            raise ValueError("unexpected trailing weights content")
    return GPT(config, parameters)


def linear(x: NDArray, weight: NDArray, bias: NDArray | None, matmul_fn) -> NDArray:
    """PyTorch Linear layout: weight[out_features, in_features]."""
    result = matmul_fn(x, weight.T)
    if bias is not None:
        result += bias
    return result


def layer_norm(x: NDArray, weight: NDArray, bias: NDArray | None) -> NDArray:
    """Normalize the last dimension with population variance and epsilon 1e-5."""
    if x.ndim != 2 or weight.shape != [x.shape[1]]:
        raise ValueError("layer_norm expects rows and one channel weight per column")
    if bias is not None and bias.shape != weight.shape:
        raise ValueError("layer_norm bias shape differs from weight")
    rows, width = x.shape[0], x.shape[1]
    out = zeros([rows, width])
    for row in range(rows):
        base = x.offset + row * x.strides[0]
        mean = 0.0
        for j in range(width):
            mean += x.data[base + j * x.strides[1]]
        mean /= float(width)
        variance = 0.0
        for j in range(width):
            centered = x.data[base + j * x.strides[1]] - mean
            variance += centered * centered
        inverse = 1.0 / math.sqrt(variance / float(width) + 1e-5)
        for j in range(width):
            normalized = (x.data[base + j * x.strides[1]] - mean) * inverse
            value = normalized * weight.data[weight.offset + j * weight.strides[0]]
            if bias is not None:
                value += bias.data[bias.offset + j * bias.strides[0]]
            out.data[row * width + j] = value
    return out


def gelu(x: NDArray) -> NDArray:
    """nn.GELU's default exact erf formula, not the tanh approximation."""
    values = x.values()
    root_two = math.sqrt(2.0)
    data = [0.5 * value * (1.0 + math.erf(value / root_two)) for value in values]
    return NDArray(data, [len(data)], [1], 0).reshape(x.shape)


def causal_attention(qkv: NDArray, batch: int, length: int, heads: int, matmul_fn) -> NDArray:
    """Scaled dot-product attention on packed Q/K/V, with no attention dropout."""
    if qkv.ndim != 2 or qkv.shape[0] != batch * length or qkv.shape[1] % 3 != 0:
        raise ValueError("attention expects packed rows of queries, keys and values")
    width = qkv.shape[1] // 3
    if heads < 1 or width % heads != 0:
        raise ValueError("attention width must be divisible by heads")
    depth = width // heads
    scale = 1.0 / math.sqrt(float(depth))
    out = zeros([batch * length, width])
    for b in range(batch):
        for h in range(heads):
            offset = qkv.offset + b * length * qkv.strides[0] + h * depth * qkv.strides[1]
            strides = [qkv.strides[0], qkv.strides[1]]
            query = NDArray(qkv.data, [length, depth], strides, offset)
            key = NDArray(qkv.data, [length, depth], strides, offset + width * qkv.strides[1])
            value = NDArray(qkv.data, [length, depth], strides, offset + 2 * width * qkv.strides[1])
            scores = matmul_fn(query, key.T)
            probabilities = zeros([length, length])
            for row in range(length):
                maximum = scores[row, 0] * scale
                for column in range(1, row + 1):
                    maximum = max(maximum, scores[row, column] * scale)
                denominator = 0.0
                for column in range(row + 1):
                    probability = math.exp(scores[row, column] * scale - maximum)
                    probabilities.data[row * length + column] = probability
                    denominator += probability
                for column in range(row + 1):
                    probabilities.data[row * length + column] /= denominator
            context = matmul_fn(probabilities, value)
            for row in range(length):
                base = (b * length + row) * width + h * depth
                for j in range(depth):
                    out.data[base + j] = context[row, j]
    return out


def embedding(model: GPT, tokens: list[int], batch: int, length: int) -> NDArray:
    config = model.config
    if batch < 1 or length < 1 or length > config.block_size or len(tokens) != batch * length:
        raise ValueError("input shape must be positive B*T within the context length")
    token_weight = model.parameters["transformer.wte.weight"]
    position_weight = model.parameters["transformer.wpe.weight"]
    out = zeros([batch * length, config.n_embd])
    for row in range(batch * length):
        token = tokens[row]
        if token < 0 or token >= config.vocab_size:
            raise ValueError("token outside vocabulary")
        position = row % length
        for j in range(config.n_embd):
            out.data[row * config.n_embd + j] = token_weight[token, j] + position_weight[position, j]
    return out


def _cache(cache: dict[str, NDArray] | None, name: str, value: NDArray) -> None:
    if cache is not None:
        cache[name] = value


def forward_hidden_with_backend(model: GPT, tokens: list[int], batch: int, length: int,
                                matmul_fn, cache: dict[str, NDArray] | None = None) -> NDArray:
    """Shared architecture; optional training cache retains pre-projection activations."""
    x = embedding(model, tokens, batch, length)
    parameters = model.parameters
    for i in range(model.config.n_layer):
        prefix = f"transformer.h.{i}."
        key = str(i)
        _cache(cache, key + ".input", x)
        norm1 = layer_norm(x, parameters[prefix + "ln_1.weight"], parameters.get(prefix + "ln_1.bias"))
        _cache(cache, key + ".norm1", norm1)
        qkv = linear(norm1, parameters[prefix + "attn.c_attn.weight"], parameters.get(prefix + "attn.c_attn.bias"), matmul_fn)
        _cache(cache, key + ".qkv", qkv)
        attention = causal_attention(qkv, batch, length, model.config.n_head, matmul_fn)
        _cache(cache, key + ".attention", attention)
        x = x + linear(attention, parameters[prefix + "attn.c_proj.weight"], parameters.get(prefix + "attn.c_proj.bias"), matmul_fn)
        _cache(cache, key + ".residual", x)
        norm2 = layer_norm(x, parameters[prefix + "ln_2.weight"], parameters.get(prefix + "ln_2.bias"))
        _cache(cache, key + ".norm2", norm2)
        fc = linear(norm2, parameters[prefix + "mlp.c_fc.weight"], parameters.get(prefix + "mlp.c_fc.bias"), matmul_fn)
        _cache(cache, key + ".fc", fc)
        activated = gelu(fc)
        _cache(cache, key + ".gelu", activated)
        x = x + linear(activated, parameters[prefix + "mlp.c_proj.weight"], parameters.get(prefix + "mlp.c_proj.bias"), matmul_fn)
    _cache(cache, "final_input", x)
    result = layer_norm(x, parameters["transformer.ln_f.weight"], parameters.get("transformer.ln_f.bias"))
    _cache(cache, "final_norm", result)
    return result


def output_projection(model: GPT, hidden: NDArray, batch: int, length: int,
                      matmul_fn, last_only: bool = False) -> NDArray:
    if last_only:
        width = model.config.n_embd
        hidden = NDArray(hidden.data, [batch, width], [length * hidden.strides[0], hidden.strides[1]],
                         hidden.offset + (length - 1) * hidden.strides[0])
        length = 1
    return matmul_fn(hidden, model.parameters["transformer.wte.weight"].T).reshape([batch, length, model.config.vocab_size])


def forward_with_backend(model: GPT, tokens: list[int], batch: int, length: int,
                         matmul_fn, last_only: bool = False) -> NDArray:
    """Use a nonmutating matrix backend with fresh results; last_only matches inference."""
    hidden = forward_hidden_with_backend(model, tokens, batch, length, matmul_fn)
    return output_projection(model, hidden, batch, length, matmul_fn, last_only)


def forward(model: GPT, tokens: list[int], batch: int, length: int, last_only: bool = False) -> NDArray:
    return forward_with_backend(model, tokens, batch, length, matmul, last_only)


def cross_entropy(logits: NDArray, targets: list[int], ignore_index: int = -1) -> float:
    """Mean stable log-softmax loss; all ignored targets return NaN as PyTorch does."""
    if logits.ndim != 3 or len(targets) != logits.shape[0] * logits.shape[1]:
        raise ValueError("targets must match the batch and time dimensions of logits")
    width = logits.shape[2]
    rows = logits.reshape([-1, width])
    loss = 0.0
    count = 0
    for row in range(len(targets)):
        target = targets[row]
        if target == ignore_index:
            continue
        if target < 0 or target >= width:
            raise ValueError("target outside vocabulary")
        maximum = rows[row, 0]
        for j in range(1, width):
            maximum = max(maximum, rows[row, j])
        denominator = 0.0
        for j in range(width):
            denominator += math.exp(rows[row, j] - maximum)
        loss += math.log(denominator) - (rows[row, target] - maximum)
        count += 1
    return loss / float(count) if count > 0 else math.nan
