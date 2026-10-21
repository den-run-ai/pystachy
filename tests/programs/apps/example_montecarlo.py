# examples/montecarlo: Monte Carlo estimates from seeded random.Random generators, as CPython
# draws them: each estimator over several seeds and sample counts, main() with its defaults
# scaled down, and its usage errors, whose last line goes to stderr
from random import Random

import montecarlo

for seed in [0, 1, 42, -7, 2**40]:
    rng = Random(seed)
    print(seed, montecarlo.estimate_pi(rng, 1000), montecarlo.walk_distance(rng, 20, 100),
          montecarlo.shared_birthday(rng, 300, 23), montecarlo.shared_birthday(rng, 50, 1))
    data = [rng.gammavariate(2.0, 1.5) for _ in range(30)]
    print(montecarlo.bootstrap_mean(rng, data, 40), montecarlo.bootstrap_mean(rng, [2.5], 3))
print(montecarlo.exact_birthday(1), montecarlo.exact_birthday(23), montecarlo.exact_birthday(60))
print(montecarlo.main(["42", "20000"]), montecarlo.main(["7", "1000"]))
print(montecarlo.main(["1", "2", "3"]), montecarlo.main(["1", "999"]))
