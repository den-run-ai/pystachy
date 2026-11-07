# Scoring with a runtime-selected callback

Write the reduction once, with an ordinary `Callable` argument:

```python
from scoring import absolute_error, score, squared_error

losses = [squared_error, absolute_error]
print(score(losses[choice], predicted, expected))
```

[`scoring.py`](scoring.py) contains the two loss functions and one small reduction.
The compiler can generate bounded callback specializations and their entry guards.
Closures, bound methods and other callbacks keep the normal call path. Application
code does not declare variants, compare function identities or route fallbacks.

[`demo.py`](demo.py) selects its loss function from the command line:

```sh
./pystachy run examples/guarded_score/demo.py 0  # squared error: 5.0
./pystachy run examples/guarded_score/demo.py 1  # absolute error: 3.0
python3 examples/guarded_score/demo.py 1
```

The lists must initially have equal lengths. The reduction visits the live lists
in order, so callback mutations, effects and exceptions retain Python semantics.
The numeric annotations establish storage types; the optimization recovers the
callback target inside the compiler.

Measurement controls, raw evidence and limitations live in
[`bench/guarded_callbacks`](../../bench/guarded_callbacks/README.md).
