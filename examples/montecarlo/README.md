# montecarlo: seeded Monte Carlo estimates

Estimate pi, the spread of random walks, the birthday-problem probability and a bootstrap
confidence interval with [`random`](../../lib/compatibility.md#random): `random()`, `choice()`,
`randrange()`, `gammavariate()` and `choices()` of one seeded `random.Random`, and
`statistics.fmean`.

## Run

From this directory, with the built `pystachy` command on `PATH`:

```sh
python3 montecarlo.py 42 1000000
pystachy build montecarlo.py -o montecarlo
./montecarlo 42 1000000
```

```
seed 42, N 1000000
pi: 3.140592
mean squared distance of 1000 steps: 1002.322
shared birthday among 23: 0.5051 exact 0.5072972343239857
mean of 200 gamma(2, 1.5) variates: 3.2216, 95% interval 2.9449 to 3.5349
```

The arguments are the seed (default 42) and the number of samples N (default 1,000,000, at
least 1,000): N points, N // 1000 walks of 1000 steps, N // 100 groups of 23 birthdays and
N // 1000 bootstrap resamples. `random.Random(seed)` draws CPython's numbers, so CPython and
the executable print the same estimates for a seed.

## Recorded benchmark

Measured on a 4-core x86-64 VM with LLVM 18.1.3 and CPython 3.13.16, with the compiler of commit
`bdc20a2` and the `random` library added with this example; median of five runs each, including
startup; seed 42. Other jobs shared the host (load average about 20), so the CPU (user + system)
times are the steadier comparison.

| Samples | CPython wall | AOT wall | Speedup | CPython CPU | AOT CPU | Speedup |
|---|---:|---:|---:|---:|---:|---:|
| 1M | 1.378 s | 0.220 s | 6.3× | 0.499 s | 0.071 s | 7.0× |
| 10M | 12.391 s | 1.817 s | 6.8× | 4.537 s | 0.719 s | 6.3× |

Both print the same estimates. Timed alone, the walks gain most (about 9×): `choice()` runs
`_randbelow()`, Python code in CPython, which the executable compiles together with the Mersenne
Twister of `_pyrandom`. The pi estimate, two `random()` calls per point, gains about 4× against
CPython's C generator; the bootstrap's resampling and `fmean()`, under 2×.

## Checks and reproduction

`tests/programs/apps/example_montecarlo.py` compares each estimator over five seeds, `main()` and its usage
errors with CPython.

```sh
python3 -I bench.py ../../pystachy 5
```

The benchmark writes its executable to `build/montecarlo/` at the repository root. Results
depend on workload and host; see [the performance guide](../../docs/performance.md).
