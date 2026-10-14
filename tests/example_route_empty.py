# Empty traces are accepted in streaming and in-memory modes, with deterministic zero
# routing time instead of division by zero. Cache statistics and destination totals agree.
import os
import tempfile
import route

d = tempfile.mkdtemp()
p = d + "/empty.tsv"
with open(p, "w") as f:
    f.write("")
modes: list[list[str]] = [[], ["--names"], ["--no-cache"], ["--fnmatch"]]
for opts in modes:
    print(opts)
    route.run("examples/route/rules.txt", p, opts)
    route.run("examples/route/rules.txt", p, opts + ["--in-memory"])
os.remove(p)
os.rmdir(d)
