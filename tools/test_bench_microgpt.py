"""Independent AST-only extraction: execute no dataset/model/training top level."""
import ast
import hashlib
import unittest

import bench_microgpt as bench
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / 'bench' / 'microgpt'


def extract(path):
    tree = ast.parse(path.read_text(), filename=str(path))
    keep = [ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0),
            ast.Import(names=[ast.alias(name='math')])]
    keep += [node for node in tree.body if
             (isinstance(node, ast.ClassDef) and node.name == 'Value') or
             (isinstance(node, ast.FunctionDef) and node.name in
              {'value_sum', 'linear', 'softmax', 'rmsnorm'})]
    scope = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=keep, type_ignores=[])), str(path), 'exec'), scope)
    return scope


original = extract(BENCH / 'upstream' / 'microgpt.py')
adapted = extract(BENCH / 'microgpt.py')


class Ops:
    def __init__(self, scope):
        self.scope = scope
        self.V = scope['Value']
        self.adapted = 'value_sum' in scope

    def add(self, left, right):
        if self.adapted and not isinstance(right, self.V):
            right = self.V(float(right))
        return left + right

    def mul(self, left, right):
        if self.adapted and not isinstance(right, self.V):
            right = self.V(float(right))
        return left * right

    def power(self, value, exponent):
        return value.__pow__(float(exponent)) if self.adapted else value ** exponent

    def div(self, left, right):
        if self.adapted and not isinstance(right, self.V):
            return left.divide_float(float(right))
        return left / right

    def sum(self, values):
        return self.scope['value_sum'](values) if self.adapted else sum(values)


def graph(root):
    """Canonical preorder preserves edges, repeated-child identity and sharing."""
    seen, records = {}, []

    def visit(node):
        if id(node) in seen:
            return seen[id(node)]
        index = len(records)
        seen[id(node)] = index
        records.append(None)
        children = [visit(child) for child in node._children]
        records[index] = {
            'data': float(node.data), 'grad': float(node.grad),
            'local_grads': [float(g) for g in node._local_grads], 'children': children,
        }
        return index
    visit(root)
    return records


def shared_diamond(o, x, y, z):
    shared = x * y
    return (shared + z) * (shared + x)


def branch(o, x, y, z):
    q = o.add(x, 0.125)
    return o.power(q, -0.5) + (q * z).log()


def eager_attention(o, x, y, z):
    q = [x, y]
    keys = [[z, x], [y, z]]
    values = [[x, z], [z, y]]
    logits = []
    for t in range(len(keys)):
        products = [q[j] * keys[t][j] for j in range(2)] if o.adapted else (q[j] * keys[t][j] for j in range(2))
        logits.append(o.div(o.sum(products), 2**0.5))
    weights = o.scope['softmax'](logits)
    heads = []
    for j in range(2):
        products = [weights[t] * values[t][j] for t in range(2)] if o.adapted else (weights[t] * values[t][j] for t in range(2))
        heads.append(o.sum(products))
    return o.sum(heads)


def reflected_loss_average(o, x, y, z):
    total = o.sum([x, y, z])
    return o.mul(total, 1 / 3) if o.adapted else (1 / 3) * total


cases = {
    'eager_attention': eager_attention,
    'reflected_loss_average': reflected_loss_average,
    'add': lambda o, x, y, z: x + y,
    'scalar_add': lambda o, x, y, z: o.add(x, 0.125),
    'scalar_subtract': lambda o, x, y, z: x - 0.125,
    'shared_diamond': shared_diamond,
    'shared_branch': branch,
    'repeated_child_multiply': lambda o, x, y, z: x * x,
    'repeated_child_add': lambda o, x, y, z: x + x,
    'scalar_multiply': lambda o, x, y, z: o.mul(x, -1.0),
    'negative': lambda o, x, y, z: -x,
    'power_negative': lambda o, x, y, z: o.power(x, -0.5),
    'power_positive': lambda o, x, y, z: o.power(x, 2),
    'log_exp': lambda o, x, y, z: (x.log() + y).exp(),
    'relu_positive': lambda o, x, y, z: x.relu(),
    'relu_negative': lambda o, x, y, z: y.relu(),
    'relu_zero': lambda o, x, y, z: o.V(0.0).relu(),
    'constant': lambda o, x, y, z: o.V(2.0),
    'scalar_division': lambda o, x, y, z: o.div(x, 2),
    'value_division': lambda o, x, y, z: o.div(x, z),
    'sum_single': lambda o, x, y, z: o.sum([x]),
    'sum_shared': lambda o, x, y, z: o.sum([x, y, x, z]),
    'sum_generator': lambda o, x, y, z: o.sum(v * v for v in [x, y, z]),
    'softmax': lambda o, x, y, z: o.scope['softmax']([x, y, z])[1],
    'rmsnorm': lambda o, x, y, z: o.scope['rmsnorm']([x, y, z])[1],
    'linear': lambda o, x, y, z: o.scope['linear']([x, y], [[z, x], [y, z]])[0],
}
class MicroGPTTests(unittest.TestCase):
    def test_graph_math_sharing_and_gradient_order(self):
        for name, build in cases.items():
            with self.subTest(case=name):
                outcomes = []
                for scope in (original, adapted):
                    o = Ops(scope)
                    params = [o.V(0.7), o.V(-0.2), o.V(1.3)]
                    result = build(o, *params)
                    before = graph(result)
                    result.backward()
                    outcomes.append((before, graph(result), [float(p.grad) for p in params]))
                self.assertEqual(outcomes[0], outcomes[1])

    def test_source_pin_and_measurement_markers(self):
        raw = (BENCH / 'upstream' / 'microgpt.py').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), bench.UPSTREAM_SHA256)
        for path in (BENCH / 'upstream' / 'microgpt.py', BENCH / 'microgpt.py'):
            source = bench.instrument(path.read_text())
            self.assertIn('num_steps = 1000', source)
            self.assertIn('for step in range(_bench_steps):', source)
            compile(source, str(path), 'exec')

    def test_vectors_are_compared_elementwise_and_nonfinite_rejected(self):
        with self.assertRaises(ValueError):
            bench.compare({'gradients': [1.0, 2.0, 3.0]}, {'gradients': [3.0, 2.0, 1.0]})
        with self.assertRaises(ValueError):
            bench.compare({'loss': float('nan')}, {'loss': 1.0})
        with self.assertRaises(ValueError):
            bench.compare({'loss': True}, {'loss': 1.0})
        with self.assertRaises(ValueError):
            bench.compare({'parameters': [1.0]}, {'parameters': [1.0, 2.0]})
        with self.assertRaises(ValueError):
            bench.parse_output('', 1, 1, False)


if __name__ == '__main__':
    unittest.main()
