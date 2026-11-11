"""Small seeded sampling checks; timing and statistical workloads stay separate."""
from random import Random

import montecarlo
import pytest


# Exact 100-point results recorded with CPython 3.13.16's Random.
@pytest.mark.parametrize("seed,expected", [(0, 3.04), (1, 3.2), (42, 3.12)])
def test_seeded_sampling_repeats_and_stays_bounded(seed: int, expected: float):
    first = montecarlo.estimate_pi(Random(seed), 100)
    assert first == expected
    assert first == montecarlo.estimate_pi(Random(seed), 100)
    assert 0.0 <= first <= 4.0
    assert montecarlo.walk_distance(Random(seed), 10, 0) == 0.0
    assert montecarlo.shared_birthday(Random(seed), 10, 1) == 0.0


def test_exact_probabilities_and_constant_bootstrap():
    assert montecarlo.exact_birthday(0) == 0.0
    assert montecarlo.exact_birthday(1) == 0.0
    assert montecarlo.exact_birthday(366) == 1.0
    assert montecarlo.bootstrap_mean(Random(42), [2.5], 3) == (2.5, 2.5)
