"""Analytic CPU float64 backward and AdamW for the dropout-free nanoGPT example.

This deliberately follows one model rather than providing general tensor autograd.
The embedding and output projection share a single parameter and gradient.
"""
import math

from ndarray import NDArray, matmul, true_divide, zeros
from model import GPT, cross_entropy, forward_hidden_with_backend


class TrainingResult:
    def __init__(self, logits: NDArray, loss: float, gradients: dict[str, NDArray]) -> None:
        self.logits = logits
        self.loss = loss
        self.gradients = gradients


def linear_backward(x: NDArray, weight: NDArray, dy: NDArray, matmul_fn) -> tuple[NDArray, NDArray, NDArray]:
    """Backward for x @ weight.T + bias; inputs are contiguous row matrices."""
    dx = matmul_fn(dy, weight)
    dw = matmul_fn(dy.T, x)
    db = zeros([weight.shape[0]])
    for row in range(dy.shape[0]):
        for col in range(dy.shape[1]):
            db.data[col] += dy.data[row * dy.shape[1] + col]
    return dx, dw, db


def layer_norm_backward(x: NDArray, weight: NDArray, dy: NDArray) -> tuple[NDArray, NDArray, NDArray]:
    """LayerNorm with epsilon 1e-5 and population variance, as upstream."""
    rows, width = x.shape[0], x.shape[1]
    dx = zeros([rows, width])
    dw = zeros([width])
    db = zeros([width])
    for row in range(rows):
        start = row * width
        mean = 0.0
        for col in range(width):
            mean += x.data[start + col]
        mean /= width
        variance = 0.0
        for col in range(width):
            centered = x.data[start + col] - mean
            variance += centered * centered
        inv_std = 1.0 / math.sqrt(variance / width + 1e-5)
        sum_dy = 0.0
        sum_dy_norm = 0.0
        for col in range(width):
            normalized = (x.data[start + col] - mean) * inv_std
            grad = dy.data[start + col]
            scaled = grad * weight.data[col]
            sum_dy += scaled
            sum_dy_norm += scaled * normalized
            dw.data[col] += grad * normalized
            db.data[col] += grad
        for col in range(width):
            normalized = (x.data[start + col] - mean) * inv_std
            scaled = dy.data[start + col] * weight.data[col]
            dx.data[start + col] = inv_std * (scaled - sum_dy / width - normalized * sum_dy_norm / width)
    return dx, dw, db


def gelu_backward(x: NDArray, dy: NDArray) -> NDArray:
    dx = zeros(x.shape)
    inv_sqrt_two = 1.0 / math.sqrt(2.0)
    inv_sqrt_two_pi = 1.0 / math.sqrt(2.0 * math.pi)
    for i in range(x.size):
        value = x.data[i]
        derivative = 0.5 * (1.0 + math.erf(value * inv_sqrt_two))
        derivative += value * math.exp(-0.5 * value * value) * inv_sqrt_two_pi
        dx.data[i] = dy.data[i] * derivative
    return dx


def cross_entropy_backward(logits: NDArray, targets: list[int]) -> NDArray:
    """Mean cross-entropy gradient, ignoring -1; all ignored gives zero gradients."""
    width = logits.shape[-1]
    rows = logits.size // width
    if len(targets) != rows:
        raise ValueError("target count does not match logits")
    count = 0
    for target in targets:
        if target != -1:
            if target < 0 or target >= width:
                raise ValueError("target is outside the vocabulary")
            count += 1
    result = zeros([rows, width])
    if count == 0:
        return result
    for row in range(rows):
        target = targets[row]
        if target == -1:
            continue
        start = row * width
        maximum = logits.data[start]
        for col in range(1, width):
            maximum = max(maximum, logits.data[start + col])
        denominator = 0.0
        for col in range(width):
            value = math.exp(logits.data[start + col] - maximum)
            result.data[start + col] = value
            denominator += value
        for col in range(width):
            result.data[start + col] /= denominator
        result.data[start + target] -= 1.0
        for col in range(width):
            result.data[start + col] /= count
    return result


def attention_backward(qkv: NDArray, dy: NDArray, batch: int, length: int, heads: int, matmul_fn) -> NDArray:
    """Recompute each head's causal probabilities from its cached QKV projection."""
    width = qkv.shape[1] // 3
    head_size = width // heads
    scale = 1.0 / math.sqrt(float(head_size))
    result = zeros(qkv.shape)
    for b in range(batch):
        for head in range(heads):
            q = zeros([length, head_size])
            k = zeros([length, head_size])
            v = zeros([length, head_size])
            dout = zeros([length, head_size])
            for t in range(length):
                qkv_start = (b * length + t) * 3 * width + head * head_size
                out_start = (b * length + t) * width + head * head_size
                for d in range(head_size):
                    dst = t * head_size + d
                    q.data[dst] = qkv.data[qkv_start + d]
                    k.data[dst] = qkv.data[qkv_start + width + d]
                    v.data[dst] = qkv.data[qkv_start + 2 * width + d]
                    dout.data[dst] = dy.data[out_start + d]
            scores = matmul_fn(q, k.T)
            probabilities = zeros([length, length])
            for t in range(length):
                start = t * length
                maximum = scores.data[start] * scale
                for s in range(1, t + 1):
                    maximum = max(maximum, scores.data[start + s] * scale)
                denominator = 0.0
                for s in range(t + 1):
                    value = math.exp(scores.data[start + s] * scale - maximum)
                    probabilities.data[start + s] = value
                    denominator += value
                for s in range(t + 1):
                    probabilities.data[start + s] /= denominator
            dv = matmul_fn(probabilities.T, dout)
            dp = matmul_fn(dout, v.T)
            ds = zeros([length, length])
            for t in range(length):
                start = t * length
                dot = 0.0
                for s in range(t + 1):
                    dot += dp.data[start + s] * probabilities.data[start + s]
                for s in range(t + 1):
                    ds.data[start + s] = scale * probabilities.data[start + s] * (dp.data[start + s] - dot)
            dq = matmul_fn(ds, k)
            dk = matmul_fn(ds.T, q)
            for t in range(length):
                start = (b * length + t) * 3 * width + head * head_size
                for d in range(head_size):
                    src = t * head_size + d
                    result.data[start + d] = dq.data[src]
                    result.data[start + width + d] = dk.data[src]
                    result.data[start + 2 * width + d] = dv.data[src]
    return result


def _linear_grad(model: GPT, name: str, x: NDArray, dy: NDArray, gradients: dict[str, NDArray], matmul_fn) -> NDArray:
    dx, dw, db = linear_backward(x, model.parameters[name + ".weight"], dy, matmul_fn)
    gradients[name + ".weight"] = dw
    if model.config.bias:
        gradients[name + ".bias"] = db
    return dx


def _norm_grad(model: GPT, name: str, x: NDArray, dy: NDArray, gradients: dict[str, NDArray]) -> NDArray:
    dx, dw, db = layer_norm_backward(x, model.parameters[name + ".weight"], dy)
    gradients[name + ".weight"] = dw
    if model.config.bias:
        gradients[name + ".bias"] = db
    return dx


def loss_and_grad_with_backend(model: GPT, tokens: list[int], targets: list[int], batch: int, length: int,
                               matmul_fn, linear_fn=None) -> TrainingResult:
    # linear_fn, as forward_hidden_with_backend takes it, computes only the forward
    # projections; every backward product uses matmul_fn.
    for parameter in model.parameters.values():
        if not parameter.whole():
            raise ValueError("training parameters must be whole contiguous arrays")
    cache: dict[str, NDArray] = {}
    hidden = forward_hidden_with_backend(model, tokens, batch, length, matmul_fn, cache, linear_fn)
    embedding_weight = model.parameters["transformer.wte.weight"]
    logits = matmul_fn(hidden, embedding_weight.T).reshape([batch, length, model.config.vocab_size])
    loss = cross_entropy(logits, targets)
    dlogits = cross_entropy_backward(logits, targets)
    # Start in model parameter order; replace entries as each adjoint is computed.
    gradients: dict[str, NDArray] = {}
    for name, parameter in model.parameters.items():
        gradients[name] = zeros(parameter.shape)
    dx, dwte, _ = linear_backward(hidden, embedding_weight, dlogits, matmul_fn)
    dx = _norm_grad(model, "transformer.ln_f", cache["final_input"], dx, gradients)
    layer = model.config.n_layer - 1
    while layer >= 0:
        key = str(layer)
        name = "transformer.h." + key
        # Backward through the MLP branch, then its residual addition.
        dgelu = _linear_grad(model, name + ".mlp.c_proj", cache[key + ".gelu"], dx, gradients, matmul_fn)
        dfc = gelu_backward(cache[key + ".fc"], dgelu)
        dnorm2 = _linear_grad(model, name + ".mlp.c_fc", cache[key + ".norm2"], dfc, gradients, matmul_fn)
        dx = dx + _norm_grad(model, name + ".ln_2", cache[key + ".residual"], dnorm2, gradients)
        # Backward through attention, then the other residual addition.
        dattn = _linear_grad(model, name + ".attn.c_proj", cache[key + ".attention"], dx, gradients, matmul_fn)
        dqkv = attention_backward(cache[key + ".qkv"], dattn, batch, length, model.config.n_head, matmul_fn)
        dnorm1 = _linear_grad(model, name + ".attn.c_attn", cache[key + ".norm1"], dqkv, gradients, matmul_fn)
        dx = dx + _norm_grad(model, name + ".ln_1", cache[key + ".input"], dnorm1, gradients)
        layer -= 1
    width = model.config.n_embd
    dwpe = gradients["transformer.wpe.weight"]
    for row in range(batch * length):
        for col in range(width):
            grad = dx.data[row * width + col]
            dwte.data[tokens[row] * width + col] += grad
            dwpe.data[(row % length) * width + col] += grad
    gradients["transformer.wte.weight"] = dwte
    return TrainingResult(logits, loss, gradients)


def loss_and_grad(model: GPT, tokens: list[int], targets: list[int], batch: int, length: int) -> TrainingResult:
    return loss_and_grad_with_backend(model, tokens, targets, batch, length, matmul)


class AdamW:
    def __init__(self, model: GPT, lr: float = 0.001, beta1: float = 0.9, beta2: float = 0.999,
                 eps: float = 1e-8, weight_decay: float = 0.1) -> None:
        if not math.isfinite(lr) or lr < 0.0:
            raise ValueError("learning rate must be finite and nonnegative")
        if not (0.0 <= beta1 < 1.0) or not (0.0 <= beta2 < 1.0):
            raise ValueError("AdamW betas must lie in [0, 1)")
        if not math.isfinite(eps) or eps < 0.0:
            raise ValueError("AdamW epsilon must be finite and nonnegative")
        if not math.isfinite(weight_decay) or weight_decay < 0.0:
            raise ValueError("weight decay must be finite and nonnegative")
        self.model = model
        self.lr = lr
        self.beta1 = beta1
        self.beta2 = beta2
        self.eps = eps
        self.weight_decay = weight_decay
        self.step_index = 0
        self.first_moment: dict[str, NDArray] = {}
        self.second_moment: dict[str, NDArray] = {}
        for name, parameter in model.parameters.items():
            if not parameter.whole():
                raise ValueError("training parameters must be whole contiguous arrays")
            self.first_moment[name] = zeros(parameter.shape)
            self.second_moment[name] = zeros(parameter.shape)

    def step(self, gradients: dict[str, NDArray]) -> None:
        if len(gradients) != len(self.model.parameters):
            raise ValueError("gradient names must match model parameters")
        # Validate before updating anything, so a malformed gradient cannot partly step.
        for name, parameter in self.model.parameters.items():
            if name not in gradients:
                raise ValueError("gradient names must match model parameters")
            if gradients[name].shape != parameter.shape or not gradients[name].whole():
                raise ValueError("gradients must be whole arrays of the parameter shape")
        self.step_index += 1
        correction1 = 1.0 - self.beta1 ** self.step_index
        correction2_sqrt = math.sqrt(1.0 - self.beta2 ** self.step_index)
        step_size = self.lr / correction1
        for name, parameter in self.model.parameters.items():
            gradient = gradients[name]
            first = self.first_moment[name]
            second = self.second_moment[name]
            decay = self.weight_decay if parameter.ndim >= 2 else 0.0
            for i in range(parameter.size):
                grad = gradient.data[i]
                # torch AdamW's scalar CPU path uses lerp for the first moment.
                first.data[i] += (1.0 - self.beta1) * (grad - first.data[i])
                second.data[i] = self.beta2 * second.data[i] + (1.0 - self.beta2) * grad * grad
                denominator = math.sqrt(second.data[i]) / correction2_sqrt + self.eps
                parameter.data[i] *= 1.0 - self.lr * decay
                parameter.data[i] -= true_divide(step_size * first.data[i], denominator)
