# pystachy: dynamic-any
from typing import Any


class Quiet:
    def __iter__(self):
        return missing_iter_body  # noqa: F821 - deliberately uncalled

    def __next__(self):
        return missing_next_body  # noqa: F821 - deliberately uncalled

    def __len__(self):
        return missing_len_body  # noqa: F821 - deliberately uncalled


quiet: Any = Quiet()
print('boxed unused methods')
# Unrelated dynamic consumers must not start rejecting Quiet's unused bodies.
xs: Any = [1, 2]
print(list(xs), list(iter(xs)), next(iter(xs)), sum(xs))
