"""Inspect the checked list read that a sequence-loop proof removes."""


def score_samples(samples: list[float]) -> float:
    score = 0.0
    for sample in samples:
        if sample > 0.0:
            score += sample * 0.5
    return score


print(score_samples([3.0, -1.0, 4.0]))
