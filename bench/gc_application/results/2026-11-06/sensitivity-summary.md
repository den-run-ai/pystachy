[Raw per-case records](sensitivity/) · [Structured summary](sensitivity-summary.json)

Follow-up comparisons. All elapsed changes use paired ratios; ranges are observed values, not confidence intervals.

## pacing_chaos

4 paired measured rounds; 1 warmup(s) per variant excluded; CPU 3.

| Variant | Median elapsed (s) | Median RSS (MiB) | Median native GC (ms) | Median native GC share |
| --- | ---: | ---: | ---: | ---: |
| min8 | 1.1093 | 11.62 | 9.80 | 0.82% |
| min32 | 1.1396 | 35.02 | 5.35 | 0.42% |
| min128 | 1.0883 | 133.14 | 2.80 | 0.26% |
| bdw | 1.6600 | 11.62 | — | — |

| BDWGC variant | Mode | Incremental / protection / markers | Median collections | Median stopped-world (ms) | Median heap peak (MiB) | Median allocated (MiB) |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| bdw | default | 0 / 1 / 1 | 3012 | 109.689 | 2.61 | 1803.79 |

BDWGC stopped-world intervals exclude collector work outside those intervals. They are not native GC elapsed time or GC CPU time; no GC share is computed from them.

| Candidate / control | Geomean elapsed change | Median paired change | Observed paired range | Lower elapsed rounds | Median paired RSS change |
| --- | ---: | ---: | ---: | ---: | ---: |
| min8 / min32 | -2.90% | -4.33% | -6.69% to +4.10% | 3/4 | -66.83% |
| min128 / min32 | -1.24% | +2.02% | -19.55% to +13.67% | 2/4 | +280.23% |
| bdw / min8 | +46.54% | +54.78% | +7.94% to +78.62% | 0/4 | +0.00% |
| bdw / min32 | +42.30% | +46.12% | +3.52% to +85.94% | 0/4 | -66.83% |

## pacing_float

6 paired measured rounds; 1 warmup(s) per variant excluded; CPU 3.

| Variant | Median elapsed (s) | Median RSS (MiB) | Median native GC (ms) | Median native GC share |
| --- | ---: | ---: | ---: | ---: |
| min8 | 2.1355 | 75.81 | 243.30 | 11.46% |
| min32 | 1.9085 | 65.51 | 135.00 | 7.09% |
| min128 | 1.7411 | 176.00 | 36.35 | 2.09% |

| Candidate / control | Geomean elapsed change | Median paired change | Observed paired range | Lower elapsed rounds | Median paired RSS change |
| --- | ---: | ---: | ---: | ---: | ---: |
| min8 / min32 | +9.42% | +8.15% | +4.20% to +19.93% | 0/6 | +15.71% |
| min128 / min32 | -12.88% | -14.87% | -22.90% to +0.11% | 5/6 | +168.65% |

## pacing_json_dumps

4 paired measured rounds; 1 warmup(s) per variant excluded; CPU 3.

| Variant | Median elapsed (s) | Median RSS (MiB) | Median native GC (ms) | Median native GC share |
| --- | ---: | ---: | ---: | ---: |
| min8 | 1.4333 | 12.66 | 34.00 | 2.33% |
| min32 | 1.6153 | 36.79 | 15.15 | 0.93% |
| min128 | 1.7467 | 133.79 | 8.30 | 0.48% |
| bdw | 1.8313 | 11.49 | — | — |

| BDWGC variant | Mode | Incremental / protection / markers | Median collections | Median stopped-world (ms) | Median heap peak (MiB) | Median allocated (MiB) |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| bdw | default | 0 / 1 / 1 | 1030.5 | 54.297 | 9.67 | 3503.30 |

BDWGC stopped-world intervals exclude collector work outside those intervals. They are not native GC elapsed time or GC CPU time; no GC share is computed from them.

| Candidate / control | Geomean elapsed change | Median paired change | Observed paired range | Lower elapsed rounds | Median paired RSS change |
| --- | ---: | ---: | ---: | ---: | ---: |
| min8 / min32 | -8.89% | -4.26% | -25.95% to +1.57% | 3/4 | -65.58% |
| min128 / min32 | +4.99% | +10.10% | -11.94% to +13.93% | 1/4 | +263.69% |
| bdw / min8 | +26.12% | +27.15% | +2.29% to +53.38% | 0/4 | -9.26% |
| bdw / min32 | +14.91% | +13.38% | +3.89% to +30.55% | 0/4 | -68.77% |

## pacing_json_retained

6 paired measured rounds; 1 warmup(s) per variant excluded; CPU 3.

| Variant | Median elapsed (s) | Median RSS (MiB) | Median native GC (ms) | Median native GC share |
| --- | ---: | ---: | ---: | ---: |
| min8 | 1.2363 | 229.91 | 496.10 | 40.09% |
| min32 | 1.1359 | 232.54 | 454.30 | 39.45% |
| min128 | 0.9715 | 258.41 | 283.90 | 29.17% |

| Candidate / control | Geomean elapsed change | Median paired change | Observed paired range | Lower elapsed rounds | Median paired RSS change |
| --- | ---: | ---: | ---: | ---: | ---: |
| min8 / min32 | +6.54% | +3.14% | -7.85% to +35.43% | 2/6 | -1.13% |
| min128 / min32 | -18.33% | -14.90% | -41.19% to -1.97% | 6/6 | +11.13% |

- min128: at least one native sample is shorter than one second

## pacing_raytrace

4 paired measured rounds; 1 warmup(s) per variant excluded; CPU 3.

| Variant | Median elapsed (s) | Median RSS (MiB) | Median native GC (ms) | Median native GC share |
| --- | ---: | ---: | ---: | ---: |
| min8 | 1.0870 | 11.41 | 24.05 | 2.21% |
| min32 | 1.3883 | 34.77 | 16.30 | 1.19% |
| min128 | 1.5085 | 131.14 | 11.55 | 0.77% |
| bdw | 1.8670 | 11.42 | — | — |

| BDWGC variant | Mode | Incremental / protection / markers | Median collections | Median stopped-world (ms) | Median heap peak (MiB) | Median allocated (MiB) |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| bdw | default | 0 / 1 / 1 | 11733 | 211.546 | 1.28 | 6484.22 |

BDWGC stopped-world intervals exclude collector work outside those intervals. They are not native GC elapsed time or GC CPU time; no GC share is computed from them.

| Candidate / control | Geomean elapsed change | Median paired change | Observed paired range | Lower elapsed rounds | Median paired RSS change |
| --- | ---: | ---: | ---: | ---: | ---: |
| min8 / min32 | -23.37% | -21.62% | -34.15% to -14.73% | 4/4 | -67.17% |
| min128 / min32 | +10.10% | +12.08% | +2.66% to +13.94% | 0/4 | +277.21% |
| bdw / min8 | +75.55% | +71.59% | +57.76% to +104.62% | 0/4 | +0.00% |
| bdw / min32 | +34.53% | +34.63% | +29.29% to +39.77% | 0/4 | -67.16% |

- min8: at least one native sample is shorter than one second

## union_retained_80

6 paired measured rounds; 1 warmup(s) per variant excluded; CPU 3.

| Variant | Median elapsed (s) | Median RSS (MiB) | Median native GC (ms) | Median native GC share |
| --- | ---: | ---: | ---: | ---: |
| default | 2.1193 | 231.16 | 906.90 | 42.56% |
| default_aa | 2.2023 | 231.16 | 933.70 | 42.45% |
| atomic_union | 1.9280 | 231.29 | 732.40 | 37.89% |

| Candidate / control | Geomean elapsed change | Median paired change | Observed paired range | Lower elapsed rounds | Median paired RSS change |
| --- | ---: | ---: | ---: | ---: | ---: |
| default_aa / default | +3.42% | +4.29% | -0.55% to +6.36% | 1/6 | +0.00% |
| atomic_union / default | -8.83% | -8.26% | -11.94% to -6.99% | 6/6 | +0.05% |
| atomic_union / default_aa | -11.84% | -11.09% | -15.84% to -6.63% | 6/6 | +0.05% |

- default_aa/default: identical executable bytes and settings; timing differences are control observations, not an optimization effect
