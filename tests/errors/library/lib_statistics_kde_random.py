# error: name '_kernel_invcdfs' is not defined
# lib/statistics's kde_random() stays uncompiled (lib/README.md): it sets a function's __doc__, and
# its table of kernels, of NormalDist().inv_cdf and functions of other types, is made in CPython only
import statistics

print(statistics.kde_random([1.0, 2.0, 4.0], h=1.5, seed=8675309)())
