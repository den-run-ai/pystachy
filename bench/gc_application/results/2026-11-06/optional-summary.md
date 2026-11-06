[Raw per-case records](optional/) · [Structured summary](optional-summary.json)

Elapsed and RSS changes are candidate/control − 1; negative values mean lower values. Ranges are observed paired minima/maxima, not confidence intervals.

## chaos

5 paired measured rounds; 1 warmup(s) per variant excluded; CPU 3.

| Variant | Median elapsed (s) | Median RSS (MiB) | Median native GC (ms) | Median native GC share |
| --- | ---: | ---: | ---: | ---: |
| native | 1.0722 | 35.02 | 4.30 | 0.40% |
| bdw | 1.3793 | 11.44 | — | — |
| bdw_32m | 1.3640 | 36.04 | — | — |
| bdw_incremental | 2.9329 | 11.44 | — | — |
| bdw_generational | 2.8594 | 11.44 | — | — |

| BDWGC variant | Mode | Incremental / protection / markers | Median collections | Median stopped-world (ms) | Median heap peak (MiB) | Median allocated (MiB) |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| bdw | default | 0 / 1 / 1 | 3012 | 86.773 | 2.61 | 1803.89 |
| bdw_32m | default | 0 / 1 / 1 | 69 | 8.212 | 32.00 | 1798.45 |
| bdw_incremental | incremental | 1 / 1 / 1 | 16152 | 974.125 | 3.49 | 1798.45 |
| bdw_generational | generational | 1 / 1 / 1 | 16215 | 965.819 | 3.49 | 1798.45 |

BDWGC stopped-world intervals exclude collector work outside those intervals. They are not native GC elapsed time or GC CPU time; no GC share is computed from them.

| Candidate / control | Geomean elapsed change | Median paired change | Observed paired range | Lower elapsed rounds | Median paired RSS change |
| --- | ---: | ---: | ---: | ---: | ---: |
| bdw / native | +27.51% | +28.26% | +23.53% to +31.13% | 0/5 | -67.32% |
| bdw_32m / native | +29.28% | +27.21% | +21.75% to +44.36% | 0/5 | +2.95% |
| bdw_incremental / native | +169.86% | +176.69% | +139.44% to +186.50% | 0/5 | -67.34% |
| bdw_generational / native | +174.52% | +167.21% | +156.71% to +205.74% | 0/5 | -67.32% |
| bdw_32m / bdw | +1.39% | -1.11% | -5.08% to +16.87% | 3/5 | +215.24% |
| bdw_incremental / bdw | +111.63% | +111.00% | +89.83% to +131.93% | 0/5 | +0.00% |
| bdw_generational / bdw | +115.29% | +113.39% | +103.52% to +137.67% | 0/5 | +0.00% |

## float

5 paired measured rounds; 1 warmup(s) per variant excluded; CPU 3.

| Variant | Median elapsed (s) | Median RSS (MiB) | Median native GC (ms) | Median native GC share |
| --- | ---: | ---: | ---: | ---: |
| native | 1.7179 | 65.51 | 121.00 | 7.06% |
| bdw | 1.9200 | 59.78 | — | — |
| bdw_32m | 1.8277 | 51.91 | — | — |
| bdw_incremental | 3.7072 | 78.93 | — | — |
| bdw_generational | 3.6896 | 78.92 | — | — |

| BDWGC variant | Mode | Incremental / protection / markers | Median collections | Median stopped-world (ms) | Median heap peak (MiB) | Median allocated (MiB) |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| bdw | default | 0 / 1 / 1 | 44 | 72.432 | 55.67 | 1831.13 |
| bdw_32m | default | 0 / 1 / 1 | 41 | 6.769 | 48.00 | 1831.07 |
| bdw_incremental | incremental | 1 / 1 / 1 | 433 | 1138.598 | 79.67 | 1831.08 |
| bdw_generational | generational | 1 / 1 / 1 | 433 | 1134.536 | 79.67 | 1831.08 |

BDWGC stopped-world intervals exclude collector work outside those intervals. They are not native GC elapsed time or GC CPU time; no GC share is computed from them.

| Candidate / control | Geomean elapsed change | Median paired change | Observed paired range | Lower elapsed rounds | Median paired RSS change |
| --- | ---: | ---: | ---: | ---: | ---: |
| bdw / native | +14.00% | +14.10% | +9.61% to +18.23% | 0/5 | -8.75% |
| bdw_32m / native | +7.44% | +5.85% | +3.82% to +12.55% | 0/5 | -20.77% |
| bdw_incremental / native | +117.77% | +114.62% | +107.53% to +129.62% | 0/5 | +20.48% |
| bdw_generational / native | +122.48% | +124.47% | +109.92% to +139.43% | 0/5 | +20.46% |
| bdw_32m / bdw | -5.75% | -4.81% | -11.57% to -2.65% | 5/5 | -13.17% |
| bdw_incremental / bdw | +91.03% | +93.08% | +76.76% to +101.24% | 0/5 | +32.04% |
| bdw_generational / bdw | +95.16% | +92.17% | +91.53% to +103.94% | 0/5 | +32.02% |

## json_dumps

5 paired measured rounds; 1 warmup(s) per variant excluded; CPU 3.

| Variant | Median elapsed (s) | Median RSS (MiB) | Median native GC (ms) | Median native GC share |
| --- | ---: | ---: | ---: | ---: |
| native | 1.6776 | 36.79 | 15.80 | 0.93% |
| bdw | 1.7015 | 13.82 | — | — |
| bdw_32m | 2.1572 | 35.47 | — | — |
| bdw_incremental | 5.0545 | 12.61 | — | — |
| bdw_generational | 5.1139 | 12.44 | — | — |

| BDWGC variant | Mode | Incremental / protection / markers | Median collections | Median stopped-world (ms) | Median heap peak (MiB) | Median allocated (MiB) |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| bdw | default | 0 / 1 / 1 | 621 | 48.240 | 11.91 | 3503.29 |
| bdw_32m | default | 0 / 1 / 1 | 127 | 22.042 | 32.00 | 3503.28 |
| bdw_incremental | incremental | 1 / 1 / 1 | 15467 | 1171.633 | 17.41 | 3503.28 |
| bdw_generational | generational | 1 / 1 / 1 | 15598 | 1184.199 | 17.52 | 3503.28 |

BDWGC stopped-world intervals exclude collector work outside those intervals. They are not native GC elapsed time or GC CPU time; no GC share is computed from them.

| Candidate / control | Geomean elapsed change | Median paired change | Observed paired range | Lower elapsed rounds | Median paired RSS change |
| --- | ---: | ---: | ---: | ---: | ---: |
| bdw / native | +3.92% | +2.67% | -4.49% to +18.57% | 2/5 | -62.43% |
| bdw_32m / native | +30.83% | +28.59% | +13.00% to +60.62% | 0/5 | -3.57% |
| bdw_incremental / native | +200.72% | +202.62% | +158.42% to +237.15% | 0/5 | -65.73% |
| bdw_generational / native | +213.07% | +206.17% | +179.63% to +274.21% | 0/5 | -66.18% |
| bdw_32m / bdw | +25.90% | +18.31% | +8.45% to +67.17% | 0/5 | +156.44% |
| bdw_incremental / bdw | +189.39% | +179.94% | +168.95% to +216.84% | 0/5 | +0.00% |
| bdw_generational / bdw | +201.27% | +220.57% | +143.62% to +245.01% | 0/5 | +7.08% |

## json_loads

5 paired measured rounds; 1 warmup(s) per variant excluded; CPU 3.

| Variant | Median elapsed (s) | Median RSS (MiB) | Median native GC (ms) | Median native GC share |
| --- | ---: | ---: | ---: | ---: |
| native | 2.0291 | 34.67 | 10.80 | 0.53% |
| bdw | 3.2081 | 11.55 | — | — |
| bdw_32m | 2.8998 | 36.19 | — | — |
| bdw_incremental | 8.3420 | 11.55 | — | — |
| bdw_generational | 8.3009 | 11.55 | — | — |

| BDWGC variant | Mode | Incremental / protection / markers | Median collections | Median stopped-world (ms) | Median heap peak (MiB) | Median allocated (MiB) |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| bdw | default | 0 / 1 / 1 | 21932 | 623.987 | 0.35 | 3315.19 |
| bdw_32m | default | 0 / 1 / 1 | 106 | 18.459 | 32.00 | 3314.51 |
| bdw_incremental | incremental | 1 / 1 / 1 | 37502 | 2800.419 | 0.61 | 3314.51 |
| bdw_generational | generational | 1 / 1 / 1 | 37373 | 2753.584 | 0.61 | 3314.51 |

BDWGC stopped-world intervals exclude collector work outside those intervals. They are not native GC elapsed time or GC CPU time; no GC share is computed from them.

| Candidate / control | Geomean elapsed change | Median paired change | Observed paired range | Lower elapsed rounds | Median paired RSS change |
| --- | ---: | ---: | ---: | ---: | ---: |
| bdw / native | +63.89% | +56.09% | +34.34% to +101.23% | 0/5 | -66.67% |
| bdw_32m / native | +46.28% | +44.23% | +21.43% to +71.05% | 0/5 | +4.41% |
| bdw_incremental / native | +299.50% | +310.64% | +249.52% to +325.22% | 0/5 | -66.68% |
| bdw_generational / native | +302.30% | +309.08% | +258.23% to +348.80% | 0/5 | -66.67% |
| bdw_32m / bdw | -10.74% | -9.61% | -17.28% to -6.87% | 5/5 | +213.32% |
| bdw_incremental / bdw | +143.76% | +160.17% | +111.31% to +170.56% | 0/5 | -0.03% |
| bdw_generational / bdw | +145.47% | +166.66% | +82.88% to +187.52% | 0/5 | +0.00% |

## json_retained_memory

5 paired measured rounds; 1 warmup(s) per variant excluded; CPU 3.

| Variant | Median elapsed (s) | Median RSS (MiB) | Median native GC (ms) | Median native GC share |
| --- | ---: | ---: | ---: | ---: |
| native | 1.1321 | 225.81 | 503.80 | 43.03% |
| bdw | 2.7104 | 228.38 | — | — |
| bdw_32m | 2.7592 | 233.25 | — | — |
| bdw_incremental | 4.4648 | 302.14 | — | — |
| bdw_generational | 4.1510 | 299.77 | — | — |

| BDWGC variant | Mode | Incremental / protection / markers | Median collections | Median stopped-world (ms) | Median heap peak (MiB) | Median allocated (MiB) |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| bdw | default | 0 / 1 / 1 | 30 | 1089.565 | 213.64 | 1257.25 |
| bdw_32m | default | 0 / 1 / 1 | 24 | 1172.689 | 216.26 | 1257.24 |
| bdw_incremental | incremental | 1 / 1 / 1 | 61 | 1888.390 | 299.51 | 1257.22 |
| bdw_generational | generational | 1 / 1 / 1 | 61 | 1780.936 | 299.51 | 1257.22 |

BDWGC stopped-world intervals exclude collector work outside those intervals. They are not native GC elapsed time or GC CPU time; no GC share is computed from them.

| Candidate / control | Geomean elapsed change | Median paired change | Observed paired range | Lower elapsed rounds | Median paired RSS change |
| --- | ---: | ---: | ---: | ---: | ---: |
| bdw / native | +131.98% | +135.70% | +94.28% to +174.44% | 0/5 | +1.15% |
| bdw_32m / native | +141.36% | +146.89% | +104.89% to +211.88% | 0/5 | +3.30% |
| bdw_incremental / native | +273.49% | +282.61% | +232.53% to +312.06% | 0/5 | +33.82% |
| bdw_generational / native | +269.38% | +263.17% | +197.36% to +364.92% | 0/5 | +32.75% |
| bdw_32m / bdw | +4.04% | +4.75% | -6.79% to +13.64% | 1/5 | +2.19% |
| bdw_incremental / bdw | +61.00% | +64.73% | +39.42% to +71.16% | 0/5 | +32.30% |
| bdw_generational / bdw | +59.23% | +62.19% | +32.33% to +91.19% | 0/5 | +31.33% |

## nbody

5 paired measured rounds; 1 warmup(s) per variant excluded; CPU 3.

| Variant | Median elapsed (s) | Median RSS (MiB) | Median native GC (ms) | Median native GC share |
| --- | ---: | ---: | ---: | ---: |
| native | 1.4568 | 11.40 | 0.00 | 0.00% |
| bdw | 1.4470 | 11.40 | — | — |
| bdw_32m | 1.4754 | 11.39 | — | — |
| bdw_incremental | 1.4870 | 11.40 | — | — |
| bdw_generational | 1.4674 | 11.39 | — | — |

| BDWGC variant | Mode | Incremental / protection / markers | Median collections | Median stopped-world (ms) | Median heap peak (MiB) | Median allocated (MiB) |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| bdw | default | 0 / 1 / 1 | 1 | 0.023 | 0.06 | 0.01 |
| bdw_32m | default | 0 / 1 / 1 | 1 | 0.023 | 32.00 | 0.01 |
| bdw_incremental | incremental | 1 / 1 / 1 | 2 | 0.048 | 0.06 | 0.01 |
| bdw_generational | generational | 1 / 1 / 1 | 2 | 0.046 | 0.06 | 0.01 |

BDWGC stopped-world intervals exclude collector work outside those intervals. They are not native GC elapsed time or GC CPU time; no GC share is computed from them.

| Candidate / control | Geomean elapsed change | Median paired change | Observed paired range | Lower elapsed rounds | Median paired RSS change |
| --- | ---: | ---: | ---: | ---: | ---: |
| bdw / native | +4.99% | +2.84% | -0.94% to +13.17% | 2/5 | +0.00% |
| bdw_32m / native | +2.15% | +1.01% | -3.10% to +11.01% | 2/5 | -0.03% |
| bdw_incremental / native | +3.12% | +1.33% | -8.50% to +13.83% | 2/5 | +0.00% |
| bdw_generational / native | +2.67% | +0.46% | -1.48% to +10.73% | 2/5 | -0.03% |
| bdw_32m / bdw | -2.71% | -4.46% | -12.47% to +11.07% | 3/5 | +0.00% |
| bdw_incremental / bdw | -1.79% | -4.22% | -17.35% to +13.89% | 3/5 | +0.00% |
| bdw_generational / bdw | -2.21% | +1.41% | -12.95% to +10.78% | 2/5 | -0.03% |

## raytrace

5 paired measured rounds; 1 warmup(s) per variant excluded; CPU 3.

| Variant | Median elapsed (s) | Median RSS (MiB) | Median native GC (ms) | Median native GC share |
| --- | ---: | ---: | ---: | ---: |
| native | 1.3831 | 34.77 | 18.00 | 1.37% |
| bdw | 2.2282 | 11.42 | — | — |
| bdw_32m | 2.3739 | 35.88 | — | — |
| bdw_incremental | 9.6832 | 11.42 | — | — |
| bdw_generational | 9.4549 | 11.42 | — | — |

| BDWGC variant | Mode | Incremental / protection / markers | Median collections | Median stopped-world (ms) | Median heap peak (MiB) | Median allocated (MiB) |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| bdw | default | 0 / 1 / 1 | 11733 | 251.347 | 1.28 | 6484.22 |
| bdw_32m | default | 0 / 1 / 1 | 205 | 30.481 | 32.00 | 6479.80 |
| bdw_incremental | incremental | 1 / 1 / 1 | 85572 | 3450.877 | 1.28 | 6479.71 |
| bdw_generational | generational | 1 / 1 / 1 | 85202 | 3226.081 | 0.97 | 6479.71 |

BDWGC stopped-world intervals exclude collector work outside those intervals. They are not native GC elapsed time or GC CPU time; no GC share is computed from them.

| Candidate / control | Geomean elapsed change | Median paired change | Observed paired range | Lower elapsed rounds | Median paired RSS change |
| --- | ---: | ---: | ---: | ---: | ---: |
| bdw / native | +48.19% | +49.87% | +26.43% to +73.40% | 0/5 | -67.16% |
| bdw_32m / native | +70.04% | +71.64% | +50.61% to +88.36% | 0/5 | +3.24% |
| bdw_incremental / native | +612.48% | +592.98% | +524.01% to +738.03% | 0/5 | -67.16% |
| bdw_generational / native | +589.31% | +583.62% | +565.82% to +620.62% | 0/5 | -67.16% |
| bdw_32m / bdw | +14.75% | +11.54% | -8.36% to +45.34% | 1/5 | +214.20% |
| bdw_incremental / bdw | +380.78% | +383.30% | +326.76% to +445.72% | 0/5 | +0.00% |
| bdw_generational / bdw | +365.15% | +344.28% | +291.42% to +470.00% | 0/5 | +0.00% |

## richards

5 paired measured rounds; 1 warmup(s) per variant excluded; CPU 3.

| Variant | Median elapsed (s) | Median RSS (MiB) | Median native GC (ms) | Median native GC share |
| --- | ---: | ---: | ---: | ---: |
| native | 1.3458 | 11.43 | 0.00 | 0.00% |
| bdw | 1.4505 | 11.43 | — | — |
| bdw_32m | 1.3936 | 11.43 | — | — |
| bdw_incremental | 1.3571 | 11.43 | — | — |
| bdw_generational | 1.4113 | 11.43 | — | — |

| BDWGC variant | Mode | Incremental / protection / markers | Median collections | Median stopped-world (ms) | Median heap peak (MiB) | Median allocated (MiB) |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| bdw | default | 0 / 1 / 1 | 8 | 2.770 | 6.21 | 6.40 |
| bdw_32m | default | 0 / 1 / 1 | 1 | 0.024 | 32.00 | 6.39 |
| bdw_incremental | incremental | 1 / 1 / 1 | 20 | 7.085 | 6.40 | 6.39 |
| bdw_generational | generational | 1 / 1 / 1 | 20 | 7.318 | 6.40 | 6.39 |

BDWGC stopped-world intervals exclude collector work outside those intervals. They are not native GC elapsed time or GC CPU time; no GC share is computed from them.

| Candidate / control | Geomean elapsed change | Median paired change | Observed paired range | Lower elapsed rounds | Median paired RSS change |
| --- | ---: | ---: | ---: | ---: | ---: |
| bdw / native | +5.26% | +4.25% | -4.31% to +15.61% | 1/5 | +0.00% |
| bdw_32m / native | +1.86% | +4.09% | -4.40% to +10.06% | 2/5 | +0.00% |
| bdw_incremental / native | +1.02% | +0.91% | -4.02% to +7.91% | 2/5 | +0.00% |
| bdw_generational / native | +4.70% | +4.39% | -1.96% to +13.89% | 1/5 | +0.00% |
| bdw_32m / bdw | -3.22% | -4.42% | -6.47% to -0.09% | 5/5 | +0.00% |
| bdw_incremental / bdw | -4.02% | -6.44% | -7.60% to +7.07% | 4/5 | +0.00% |
| bdw_generational / bdw | -0.53% | -1.49% | -6.33% to +9.10% | 3/5 | +0.00% |
