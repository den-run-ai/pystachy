"""
The most atomic way to train and run inference for a GPT in pure, dependency-free Python.
This file is the complete algorithm.
Everything else is just efficiency.

@karpathy
"""

# Pystachy port: recursive Value annotations are forward references.
from __future__ import annotations

import os       # os.path.exists
import math     # math.log, math.exp
import random   # random.seed, random.choices, random.gauss, random.shuffle
random.seed(42) # Let there be order among chaos

# Let there be a Dataset `docs`: list[str] of documents (e.g. a list of names)
if not os.path.exists('input.txt'):
    # Pystachy port: explicit local data replaces unsupported urllib downloads.
    raise ValueError('provide input.txt before running')
docs = [line.strip() for line in open('input.txt') if line.strip()]
random.shuffle(docs)
print(f"num docs: {len(docs)}")

# Let there be a Tokenizer to translate strings to sequences of integers ("tokens") and back
uchars = sorted(set(''.join(docs))) # unique characters in the dataset become token ids 0..n-1
BOS = len(uchars) # token id for a special Beginning of Sequence (BOS) token
vocab_size = len(uchars) + 1 # total number of unique tokens, +1 is for BOS
print(f"vocab size: {vocab_size}")

# Let there be Autograd to recursively apply the chain rule through a computation graph
class Value:
    __slots__ = ('data', 'grad', '_children', '_local_grads') # Python optimization for memory usage

    # Pystachy port: concrete floats; tuple[Value, ...] needs list storage.
    def __init__(self, data: float, children: list[Value] | None = None, local_grads: tuple[float, ...] = ()) -> None:
        self.data = data                # scalar value of this node calculated during forward pass
        self.grad = 0.0                   # derivative of the loss w.r.t. this node, calculated in backward pass
        self._children = children if children is not None else []       # children of this node in the computation graph
        self._local_grads = local_grads # local derivative of this node w.r.t. its children

    # Pystachy port: Value | float is unsupported; callers box scalar operands.
    def __add__(self, other: Value) -> Value:
        return Value(self.data + other.data, [self, other], (1.0, 1.0))

    def __mul__(self, other: Value) -> Value:
        return Value(self.data * other.data, [self, other], (other.data, self.data))

    def __pow__(self, other: float) -> Value: return Value(self.data**other, [self], (other * self.data**(other-1),))
    def log(self) -> Value: return Value(math.log(self.data), [self], (1/self.data,))
    def exp(self) -> Value: return Value(math.exp(self.data), [self], (math.exp(self.data),))
    def relu(self) -> Value: return Value(max(0.0, self.data), [self], (float(self.data > 0),))
    def __neg__(self) -> Value: return self * Value(-1.0)
    def __radd__(self, other: float) -> Value: return self + Value(other)
    def __sub__(self, other: float) -> Value: return self + Value(-other)
    def __rsub__(self, other: float) -> Value: return (-self) + Value(other)
    def __rmul__(self, other: float) -> Value: return self * Value(other)
    # Pystachy port: scalar division stays separate; call __pow__ explicitly.
    def __truediv__(self, other: Value) -> Value: return self * other.__pow__(-1.0)
    def divide_float(self, other: float) -> Value: return self * Value(other**-1)
    def __rtruediv__(self, other: float) -> Value: return self.__pow__(-1.0) * Value(other)

    def backward(self) -> None:
        # Pystachy port: type the containers captured by recursive traversal.
        topo: list[Value] = []
        visited: set[Value] = set()
        def build_topo(v: Value) -> None:
            if v not in visited:
                visited.add(v)
                for child in v._children:
                    build_topo(child)
                topo.append(v)
        build_topo(self)
        self.grad = 1.0
        for v in reversed(topo):
            for child, local_grad in zip(v._children, v._local_grads):
                child.grad += local_grad * v.grad

# Pystachy port: builtin sum rejects Value; preserve its first reflected add
# as first_value + zero, followed by accumulator + each remaining value.
def value_sum(values) -> Value:
    total: Value | None = None
    for value in values:
        if total is None:
            total = value + Value(0.0)
        else:
            total = total + value
    if total is None:
        return Value(0.0)
    return total

# Initialize the parameters, to store the knowledge of the model
n_layer = 1     # depth of the transformer neural network (number of layers)
n_embd = 16     # width of the network (embedding dimension)
block_size = 16 # maximum context length of the attention window (note: the longest name is 15 characters)
n_head = 4      # number of attention heads
head_dim = n_embd // n_head # derived dimension of each head
matrix = lambda nout, nin, std=0.08: [[Value(random.gauss(0, std)) for _ in range(nin)] for _ in range(nout)] # noqa: E731 (upstream spelling)
state_dict = {'wte': matrix(vocab_size, n_embd), 'wpe': matrix(block_size, n_embd), 'lm_head': matrix(vocab_size, n_embd)}
for i in range(n_layer):
    state_dict[f'layer{i}.attn_wq'] = matrix(n_embd, n_embd)
    state_dict[f'layer{i}.attn_wk'] = matrix(n_embd, n_embd)
    state_dict[f'layer{i}.attn_wv'] = matrix(n_embd, n_embd)
    state_dict[f'layer{i}.attn_wo'] = matrix(n_embd, n_embd)
    state_dict[f'layer{i}.mlp_fc1'] = matrix(4 * n_embd, n_embd)
    state_dict[f'layer{i}.mlp_fc2'] = matrix(n_embd, 4 * n_embd)
params = [p for mat in state_dict.values() for row in mat for p in row] # flatten params into a single list[Value]
print(f"num params: {len(params)}")

# Define the model architecture: a function mapping tokens and parameters to logits over what comes next
# Follow GPT-2, blessed among the GPTs, with minor differences: layernorm -> rmsnorm, no biases, GeLU -> ReLU
# Pystachy port: concrete container signatures and Value-aware summation.
def linear(x: list[Value], w: list[list[Value]]) -> list[Value]:
    return [value_sum(wi * xi for wi, xi in zip(wo, x)) for wo in w]

def softmax(logits: list[Value]) -> list[Value]:
    max_val = max(val.data for val in logits)
    exps = [(val - max_val).exp() for val in logits]
    total = value_sum(exps)
    return [e / total for e in exps]

def rmsnorm(x: list[Value]) -> list[Value]:
    # Pystachy port: preserve scalar boxing/division; explicit power call.
    ms = value_sum(xi * xi for xi in x).divide_float(float(len(x)))
    scale = (ms + Value(1e-5)).__pow__(-0.5)
    return [xi * scale for xi in x]

def gpt(token_id: int, pos_id: int, keys: list[list[list[Value]]], values: list[list[list[Value]]]) -> list[Value]:
    tok_emb = state_dict['wte'][token_id] # token embedding
    pos_emb = state_dict['wpe'][pos_id] # position embedding
    x = [t + p for t, p in zip(tok_emb, pos_emb)] # joint token and position embedding
    x = rmsnorm(x) # note: not redundant due to backward pass via the residual connection

    for li in range(n_layer):
        # 1) Multi-head Attention block
        x_residual = x
        x = rmsnorm(x)
        q = linear(x, state_dict[f'layer{li}.attn_wq'])
        k = linear(x, state_dict[f'layer{li}.attn_wk'])
        v = linear(x, state_dict[f'layer{li}.attn_wv'])
        keys[li].append(k)
        values[li].append(v)
        x_attn: list[Value] = [] # Pystachy port: type an empty result.
        for h in range(n_head):
            hs = h * head_dim
            q_h = q[hs:hs+head_dim]
            k_h = [ki[hs:hs+head_dim] for ki in keys[li]]
            v_h = [vi[hs:hs+head_dim] for vi in values[li]]
            # Pystachy port: nested generators reject these rebound captures.
            attn_logits = [value_sum([q_h[j] * k_h[t][j] for j in range(head_dim)]).divide_float(head_dim**0.5) for t in range(len(k_h))]
            attn_weights = softmax(attn_logits)
            head_out = [value_sum([attn_weights[t] * v_h[t][j] for t in range(len(v_h))]) for j in range(head_dim)]
            x_attn.extend(head_out)
        x = linear(x_attn, state_dict[f'layer{li}.attn_wo'])
        x = [a + b for a, b in zip(x, x_residual)]
        # 2) MLP block
        x_residual = x
        x = rmsnorm(x)
        x = linear(x, state_dict[f'layer{li}.mlp_fc1'])
        x = [xi.relu() for xi in x]
        x = linear(x, state_dict[f'layer{li}.mlp_fc2'])
        x = [a + b for a, b in zip(x, x_residual)]

    logits = linear(x, state_dict['lm_head'])
    return logits

# Let there be Adam, the blessed optimizer and its buffers
learning_rate, beta1, beta2, eps_adam = 0.01, 0.85, 0.99, 1e-8
m = [0.0] * len(params) # first moment buffer
v = [0.0] * len(params) # second moment buffer

# Repeat in sequence
num_steps = 1000 # number of training steps
for step in range(num_steps):

    # Take single document, tokenize it, surround it with BOS special token on both sides
    doc = docs[step % len(docs)]
    tokens = [BOS] + [uchars.index(ch) for ch in doc] + [BOS]
    n = min(block_size, len(tokens) - 1)

    # Forward the token sequence through the model, building up the computation graph all the way to the loss
    # Pystachy port: concrete nested empty containers.
    keys: list[list[list[Value]]] = [[] for _ in range(n_layer)]
    values: list[list[list[Value]]] = [[] for _ in range(n_layer)]
    losses: list[Value] = []
    for pos_id in range(n):
        token_id, target_id = tokens[pos_id], tokens[pos_id + 1]
        logits = gpt(token_id, pos_id, keys, values)
        probs = softmax(logits)
        loss_t = -probs[target_id].log()
        losses.append(loss_t)
    # Pystachy port: explicit reflected multiply; upstream calls sum.__rmul__.
    loss = value_sum(losses) * Value(1 / n) # final average loss over the document sequence. May yours be low.

    # Backward the loss, calculating the gradients with respect to all model parameters
    loss.backward()

    # Adam optimizer update: update the model parameters based on the corresponding gradients
    lr_t = learning_rate * (1 - step / num_steps) # linear learning rate decay
    for i, p in enumerate(params):
        m[i] = beta1 * m[i] + (1 - beta1) * p.grad
        v[i] = beta2 * v[i] + (1 - beta2) * p.grad ** 2
        m_hat = m[i] / (1 - beta1 ** (step + 1))
        v_hat = v[i] / (1 - beta2 ** (step + 1))
        p.data -= lr_t * m_hat / (v_hat ** 0.5 + eps_adam)
        p.grad = 0.0 # Pystachy port: keep the gradient field float.

    print(f"step {step+1:4d} / {num_steps:4d} | loss {loss.data:.4f}", end='\r')

# Inference: may the model babble back to us
temperature = 0.5 # in (0, 1], control the "creativity" of generated text, low to high
print("\n--- inference (new, hallucinated names) ---")
for sample_idx in range(20):
    # Pystachy port: concrete nested empty containers.
    keys: list[list[list[Value]]] = [[] for _ in range(n_layer)]
    values: list[list[list[Value]]] = [[] for _ in range(n_layer)]
    token_id = BOS
    sample: list[str] = [] # Pystachy port: type the empty text list.
    for pos_id in range(block_size):
        logits = gpt(token_id, pos_id, keys, values)
        # Pystachy port: scalar division has a concrete helper.
        probs = softmax([l.divide_float(temperature) for l in logits])
        token_id = random.choices(range(vocab_size), weights=[p.data for p in probs])[0]
        if token_id == BOS:
            break
        sample.append(uchars[token_id])
    print(f"sample {sample_idx+1:2d}: {''.join(sample)}")