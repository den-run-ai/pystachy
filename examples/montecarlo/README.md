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

<a id="recorded-benchmark"></a>
<a id="checks-and-reproduction"></a>

## Checks and benchmarks

[`example_montecarlo.py`](../../tests/programs/apps/example_montecarlo.py)
compares each estimator over five seeds, `main()` and usage errors with CPython.
The benchmark uses seed 42 with one and ten million samples and reports wall
and CPU time, including process startup.

```sh
python3 -I bench.py ../../pystachy 5
```

The executable goes to `build/montecarlo/` at the repository root.
[Earlier measurements](https://github.com/den-run-ai/pystachy/blob/f7103067545b43cdcd8ce20dc66b1571425b3a8d/examples/montecarlo/README.md#recorded-benchmark)
used compiler `bdc20a2` with the original random-library port on a heavily shared host.
See the [benchmark guidance](../README.md#benchmarks) when measuring a current build.
