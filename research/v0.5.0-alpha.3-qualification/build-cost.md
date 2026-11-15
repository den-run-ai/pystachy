# Bounded alpha.2 to alpha.3 build-cost comparison

Three alternating paired builds per workload, one CPU, warm runtime cache and program cache disabled. Every output was checked against pinned CPython before accepting timings. These are build costs, not execution-speed measurements. The timing ranges overlap; the sample does not support a general speed claim.

| Workload | Base median seconds | Candidate median seconds | Change | Peak child RSS change | Executable bytes change |
| --- | ---: | ---: | ---: | ---: | ---: |
| numeric | 0.457587 | 0.497589 | +8.74% | +0.73% | +2.91% |
| json | 10.303351 | 10.453809 | +1.46% | +0.05% | +0.04% |
| copy_float | 0.256597 | 0.279025 | +8.74% | +0.00% | +5.67% |

The archive retains every sample, output check, command, source/binary/tool identity, cache receipt, and the scope of the memory collector. Original results remain attributed to the tested b0bda81ec source.
