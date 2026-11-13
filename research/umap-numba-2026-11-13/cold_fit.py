"""Time `import umap` and one end-to-end fit in a fresh process (random init, 200 epochs)."""

import json
import sys
import time

start = time.perf_counter()
import numpy as np  # noqa: E402

import umap  # noqa: E402

imported = time.perf_counter()
with open(sys.argv[1]) as f:
    lines = f.read().split("\n")
n, dim = [int(x) for x in lines[0].split()[:2]]
X = np.array([float(x) for x in lines[1].split()], dtype=np.float32).reshape(n, dim)
loaded = time.perf_counter()
parallel = sys.argv[2] == "parallel"
model = umap.UMAP(
    n_neighbors=15, n_epochs=200, init="random", compatibility_layout=True,
    random_state=None if parallel else 42, n_jobs=-1 if parallel else 1,
)
model.fit_transform(X)
fitted = time.perf_counter()
if len(sys.argv) < 4:
    model.fit_transform(X)
again = time.perf_counter()
print(json.dumps({
    "mode": sys.argv[2], "import_s": imported - start,
    "first_fit_s": fitted - loaded, "second_fit_same_process_s": again - fitted,
}))
