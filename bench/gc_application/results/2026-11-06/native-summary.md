[Raw per-case records](native/) · [Structured summary](native-summary.json)

Elapsed and RSS changes are candidate/control − 1; negative values mean lower values. Ranges are observed paired minima/maxima, not confidence intervals.

## chaos

6 paired measured rounds; 1 warmup(s) per variant excluded; CPU 3.

| Variant | Median elapsed (s) | Median RSS (MiB) | Median native GC (ms) | Median native GC share |
| --- | ---: | ---: | ---: | ---: |
| main | 1.0540 | 35.01 | 3.65 | 0.35% |
| main_aa | 1.0403 | 35.01 | 3.70 | 0.36% |
| scalar | 1.0560 | 35.01 | 3.95 | 0.37% |
| default | 1.0760 | 35.02 | 4.00 | 0.37% |
| atomic_union | 1.0472 | 35.02 | 4.00 | 0.39% |
| block | 1.0390 | 35.02 | 4.00 | 0.38% |

| Candidate / control | Geomean elapsed change | Median paired change | Observed paired range | Lower elapsed rounds | Median paired RSS change |
| --- | ---: | ---: | ---: | ---: | ---: |
| main_aa / main | -1.53% | -1.75% | -3.58% to +0.88% | 5/6 | +0.00% |
| scalar / main | -0.75% | -1.54% | -4.52% to +6.33% | 4/6 | -0.01% |
| default / scalar | +6.06% | +5.48% | -3.80% to +26.35% | 2/6 | +0.02% |
| default / main | +5.27% | +4.05% | -3.41% to +20.64% | 1/6 | +0.01% |
| atomic_union / default | -5.73% | -3.22% | -19.81% to -0.98% | 6/6 | +0.00% |
| atomic_union / main | -0.76% | +0.37% | -4.35% to +1.34% | 2/6 | +0.01% |
| block / default | -6.12% | -4.92% | -20.72% to +5.33% | 5/6 | +0.00% |

Identical-binary A/A: median absolute paired difference 1.75%; largest observed difference 3.58%. These are descriptive observations, not significance thresholds.

- main_aa: at least one native sample is shorter than one second
- scalar: at least one native sample is shorter than one second
- block: at least one native sample is shorter than one second
- atomic_union/default: identical executable bytes and settings; timing differences are control observations, not an optimization effect

## float

6 paired measured rounds; 1 warmup(s) per variant excluded; CPU 3.

| Variant | Median elapsed (s) | Median RSS (MiB) | Median native GC (ms) | Median native GC share |
| --- | ---: | ---: | ---: | ---: |
| main | 1.8329 | 65.72 | 289.95 | 15.95% |
| main_aa | 1.8163 | 65.72 | 289.00 | 15.94% |
| scalar | 1.6911 | 65.52 | 119.15 | 7.13% |
| default | 1.6669 | 65.52 | 116.45 | 6.96% |
| atomic_union | 1.6828 | 65.51 | 116.10 | 6.93% |
| block | 1.6871 | 65.51 | 115.90 | 6.94% |

| Candidate / control | Geomean elapsed change | Median paired change | Observed paired range | Lower elapsed rounds | Median paired RSS change |
| --- | ---: | ---: | ---: | ---: | ---: |
| main_aa / main | +0.35% | +0.10% | -2.18% to +3.55% | 3/6 | +0.00% |
| scalar / main | -7.50% | -8.94% | -11.08% to +0.81% | 5/6 | -0.31% |
| default / scalar | -0.92% | -2.27% | -5.17% to +7.99% | 5/6 | +0.00% |
| default / main | -8.35% | -8.96% | -12.58% to -3.98% | 6/6 | -0.31% |
| atomic_union / default | +0.91% | +2.35% | -7.79% to +7.45% | 2/6 | -0.00% |
| atomic_union / main | -7.52% | -8.02% | -12.94% to +0.21% | 5/6 | -0.32% |
| block / default | +0.56% | -0.65% | -4.53% to +7.81% | 3/6 | -0.00% |

Identical-binary A/A: median absolute paired difference 1.78%; largest observed difference 3.55%. These are descriptive observations, not significance thresholds.

- atomic_union/default: identical executable bytes and settings; timing differences are control observations, not an optimization effect

## json_dumps

6 paired measured rounds; 1 warmup(s) per variant excluded; CPU 3.

| Variant | Median elapsed (s) | Median RSS (MiB) | Median native GC (ms) | Median native GC share |
| --- | ---: | ---: | ---: | ---: |
| main | 1.4863 | 36.91 | 12.35 | 0.84% |
| main_aa | 1.4614 | 36.91 | 12.05 | 0.84% |
| scalar | 1.5367 | 36.91 | 14.15 | 0.88% |
| default | 1.4016 | 36.79 | 12.20 | 0.88% |
| atomic_union | 1.4918 | 36.79 | 13.55 | 0.89% |
| block | 1.4875 | 36.79 | 13.40 | 0.90% |

| Candidate / control | Geomean elapsed change | Median paired change | Observed paired range | Lower elapsed rounds | Median paired RSS change |
| --- | ---: | ---: | ---: | ---: | ---: |
| main_aa / main | -2.86% | -3.00% | -13.96% to +8.13% | 4/6 | +0.00% |
| scalar / main | +6.70% | +3.29% | -12.32% to +48.17% | 2/6 | +0.00% |
| default / scalar | -10.29% | -7.20% | -34.48% to +11.97% | 5/6 | -0.34% |
| default / main | -4.28% | -3.72% | -19.04% to +8.12% | 4/6 | -0.34% |
| atomic_union / default | +4.43% | +2.87% | -12.92% to +34.66% | 3/6 | +0.00% |
| atomic_union / main | -0.04% | +1.09% | -23.16% to +24.99% | 3/6 | -0.34% |
| block / default | +5.56% | +7.44% | -6.95% to +13.13% | 1/6 | +0.00% |

Identical-binary A/A: median absolute paired difference 7.39%; largest observed difference 13.96%. These are descriptive observations, not significance thresholds.

- scalar/main: identical executable bytes and settings; timing differences are control observations, not an optimization effect
- atomic_union/default: identical executable bytes and settings; timing differences are control observations, not an optimization effect

## json_loads

6 paired measured rounds; 1 warmup(s) per variant excluded; CPU 3.

| Variant | Median elapsed (s) | Median RSS (MiB) | Median native GC (ms) | Median native GC share |
| --- | ---: | ---: | ---: | ---: |
| main | 2.0035 | 34.79 | 9.90 | 0.50% |
| main_aa | 1.9912 | 34.79 | 10.35 | 0.51% |
| scalar | 1.9849 | 34.79 | 10.35 | 0.52% |
| default | 1.9217 | 34.67 | 9.70 | 0.50% |
| atomic_union | 2.0607 | 34.79 | 11.45 | 0.54% |
| block | 1.9564 | 34.67 | 10.10 | 0.51% |

| Candidate / control | Geomean elapsed change | Median paired change | Observed paired range | Lower elapsed rounds | Median paired RSS change |
| --- | ---: | ---: | ---: | ---: | ---: |
| main_aa / main | +0.42% | +1.10% | -16.74% to +19.22% | 3/6 | +0.00% |
| scalar / main | -2.40% | -0.73% | -15.07% to +10.93% | 3/6 | +0.00% |
| default / scalar | +0.04% | -1.80% | -9.96% to +21.26% | 4/6 | -0.36% |
| default / main | -2.36% | -3.85% | -17.28% to +22.01% | 4/6 | -0.36% |
| atomic_union / default | +5.53% | +5.20% | -18.59% to +27.32% | 1/6 | +0.36% |
| atomic_union / main | +3.03% | +0.53% | -4.02% to +17.67% | 3/6 | +0.00% |
| block / default | -0.65% | +2.23% | -22.20% to +12.41% | 2/6 | +0.00% |

Identical-binary A/A: median absolute paired difference 5.49%; largest observed difference 19.22%. These are descriptive observations, not significance thresholds.

## json_retained

6 paired measured rounds; 1 warmup(s) per variant excluded; CPU 3.

| Variant | Median elapsed (s) | Median RSS (MiB) | Median native GC (ms) | Median native GC share |
| --- | ---: | ---: | ---: | ---: |
| main | 1.1191 | 232.54 | 442.35 | 38.79% |
| main_aa | 1.1333 | 232.54 | 427.90 | 38.02% |
| scalar | 1.0926 | 232.54 | 418.40 | 38.81% |
| default | 1.0788 | 232.54 | 429.70 | 39.79% |
| atomic_union | 1.0436 | 221.29 | 378.90 | 36.45% |
| block | 1.0723 | 220.91 | 414.30 | 38.34% |

| Candidate / control | Geomean elapsed change | Median paired change | Observed paired range | Lower elapsed rounds | Median paired RSS change |
| --- | ---: | ---: | ---: | ---: | ---: |
| main_aa / main | -0.26% | -2.72% | -6.04% to +10.98% | 4/6 | +0.00% |
| scalar / main | -3.30% | -5.46% | -8.19% to +5.52% | 4/6 | +0.00% |
| default / scalar | +0.12% | -1.35% | -4.29% to +8.38% | 4/6 | +0.00% |
| default / main | -3.18% | -2.10% | -11.98% to +3.85% | 3/6 | +0.00% |
| atomic_union / default | -3.98% | -2.66% | -8.20% to -0.25% | 6/6 | -4.84% |
| atomic_union / main | -7.03% | -6.36% | -13.50% to -2.03% | 6/6 | -4.84% |
| block / default | +1.74% | -0.72% | -7.49% to +17.87% | 3/6 | -5.00% |

Identical-binary A/A: median absolute paired difference 5.61%; largest observed difference 10.98%. These are descriptive observations, not significance thresholds.

- atomic_union: at least one native sample is shorter than one second
- scalar/main: identical executable bytes and settings; timing differences are control observations, not an optimization effect

## nbody

6 paired measured rounds; 1 warmup(s) per variant excluded; CPU 3.

| Variant | Median elapsed (s) | Median RSS (MiB) | Median native GC (ms) | Median native GC share |
| --- | ---: | ---: | ---: | ---: |
| main | 1.4344 | 11.31 | 0.00 | 0.00% |
| main_aa | 1.3885 | 11.31 | 0.00 | 0.00% |
| scalar | 1.4239 | 11.31 | 0.00 | 0.00% |
| default | 1.5220 | 11.32 | 0.00 | 0.00% |
| atomic_union | 1.4027 | 11.32 | 0.00 | 0.00% |
| block | 1.3752 | 11.31 | 0.00 | 0.00% |

| Candidate / control | Geomean elapsed change | Median paired change | Observed paired range | Lower elapsed rounds | Median paired RSS change |
| --- | ---: | ---: | ---: | ---: | ---: |
| main_aa / main | -4.18% | -2.82% | -13.52% to +2.73% | 5/6 | +0.02% |
| scalar / main | -1.98% | -2.15% | -10.16% to +4.92% | 4/6 | +0.00% |
| default / scalar | +5.97% | +4.93% | -3.53% to +15.23% | 1/6 | +0.10% |
| default / main | +3.87% | +8.63% | -13.33% to +11.37% | 2/6 | +0.07% |
| atomic_union / default | -8.36% | -8.08% | -14.63% to -1.12% | 6/6 | -0.07% |
| atomic_union / main | -4.81% | -4.05% | -14.30% to +1.51% | 5/6 | +0.00% |
| block / default | -9.22% | -8.26% | -17.81% to -3.75% | 6/6 | -0.10% |

Identical-binary A/A: median absolute paired difference 3.32%; largest observed difference 13.52%. These are descriptive observations, not significance thresholds.

- scalar/main: identical executable bytes and settings; timing differences are control observations, not an optimization effect
- atomic_union/default: identical executable bytes and settings; timing differences are control observations, not an optimization effect

## raytrace

6 paired measured rounds; 1 warmup(s) per variant excluded; CPU 3.

| Variant | Median elapsed (s) | Median RSS (MiB) | Median native GC (ms) | Median native GC share |
| --- | ---: | ---: | ---: | ---: |
| main | 1.2068 | 34.77 | 12.75 | 1.08% |
| main_aa | 1.2015 | 34.77 | 13.05 | 1.08% |
| scalar | 1.1991 | 34.77 | 13.55 | 1.13% |
| default | 1.2264 | 34.77 | 14.25 | 1.16% |
| atomic_union | 1.2272 | 34.77 | 14.15 | 1.15% |
| block | 1.2289 | 34.77 | 14.15 | 1.15% |

| Candidate / control | Geomean elapsed change | Median paired change | Observed paired range | Lower elapsed rounds | Median paired RSS change |
| --- | ---: | ---: | ---: | ---: | ---: |
| main_aa / main | -0.83% | -1.25% | -5.85% to +5.91% | 3/6 | +0.00% |
| scalar / main | -0.88% | -0.76% | -6.58% to +4.94% | 3/6 | +0.00% |
| default / scalar | +1.54% | +1.44% | -1.75% to +5.88% | 2/6 | +0.00% |
| default / main | +0.64% | +3.34% | -7.71% to +5.25% | 2/6 | +0.00% |
| atomic_union / default | +0.25% | +0.25% | -3.71% to +4.31% | 3/6 | +0.00% |
| atomic_union / main | +0.89% | +0.50% | -3.73% to +7.62% | 3/6 | +0.00% |
| block / default | -0.71% | -0.34% | -6.49% to +7.03% | 3/6 | +0.00% |

Identical-binary A/A: median absolute paired difference 3.10%; largest observed difference 5.91%. These are descriptive observations, not significance thresholds.

- atomic_union/default: identical executable bytes and settings; timing differences are control observations, not an optimization effect

## repair_traces

6 paired measured rounds; 1 warmup(s) per variant excluded; CPU 3.

| Variant | Median elapsed (s) | Median RSS (MiB) | Median native GC (ms) | Median native GC share |
| --- | ---: | ---: | ---: | ---: |
| main | 0.6307 | 35.17 | 2.85 | 0.46% |
| main_aa | 0.6324 | 35.11 | 2.80 | 0.44% |
| scalar | 0.6475 | 35.15 | 2.85 | 0.44% |
| default | 0.6328 | 35.11 | 2.65 | 0.42% |
| atomic_union | 0.6370 | 35.12 | 2.70 | 0.43% |
| block | 0.6455 | 35.00 | 2.70 | 0.41% |

| Candidate / control | Geomean elapsed change | Median paired change | Observed paired range | Lower elapsed rounds | Median paired RSS change |
| --- | ---: | ---: | ---: | ---: | ---: |
| main_aa / main | -0.07% | -0.89% | -3.11% to +4.23% | 4/6 | +0.00% |
| scalar / main | +1.46% | +0.85% | -2.32% to +7.22% | 3/6 | -0.07% |
| default / scalar | -2.08% | -1.72% | -9.26% to +3.23% | 4/6 | -0.01% |
| default / main | -0.65% | -1.39% | -6.65% to +8.04% | 4/6 | -0.17% |
| atomic_union / default | +1.45% | +2.45% | -5.79% to +6.18% | 2/6 | +0.02% |
| atomic_union / main | +0.79% | +0.58% | -4.08% to +7.29% | 3/6 | -0.15% |
| block / default | +1.22% | +0.82% | -2.37% to +5.36% | 3/6 | -0.34% |

Identical-binary A/A: median absolute paired difference 2.64%; largest observed difference 4.23%. These are descriptive observations, not significance thresholds.

- main: at least one native sample is shorter than one second
- main_aa: at least one native sample is shorter than one second
- scalar: at least one native sample is shorter than one second
- default: at least one native sample is shorter than one second
- atomic_union: at least one native sample is shorter than one second
- block: at least one native sample is shorter than one second

## richards

6 paired measured rounds; 1 warmup(s) per variant excluded; CPU 3.

| Variant | Median elapsed (s) | Median RSS (MiB) | Median native GC (ms) | Median native GC share |
| --- | ---: | ---: | ---: | ---: |
| main | 1.4026 | 11.31 | 0.00 | 0.00% |
| main_aa | 1.3760 | 11.33 | 0.00 | 0.00% |
| scalar | 1.3935 | 11.33 | 0.00 | 0.00% |
| default | 1.3714 | 11.33 | 0.00 | 0.00% |
| atomic_union | 1.3558 | 11.32 | 0.00 | 0.00% |
| block | 1.3488 | 11.31 | 0.00 | 0.00% |

| Candidate / control | Geomean elapsed change | Median paired change | Observed paired range | Lower elapsed rounds | Median paired RSS change |
| --- | ---: | ---: | ---: | ---: | ---: |
| main_aa / main | -2.66% | -1.89% | -15.89% to +11.38% | 4/6 | -0.03% |
| scalar / main | -1.56% | +1.66% | -17.07% to +11.10% | 3/6 | +0.02% |
| default / scalar | -2.12% | -1.33% | -7.62% to +1.23% | 5/6 | +0.00% |
| default / main | -3.66% | -1.85% | -18.12% to +9.55% | 4/6 | -0.02% |
| atomic_union / default | -0.12% | -0.64% | -4.88% to +7.54% | 4/6 | +0.00% |
| atomic_union / main | -3.77% | -2.29% | -18.40% to +7.08% | 4/6 | +0.00% |
| block / default | +0.74% | +3.66% | -8.88% to +8.05% | 2/6 | -0.02% |

Identical-binary A/A: median absolute paired difference 4.79%; largest observed difference 15.89%. These are descriptive observations, not significance thresholds.

- atomic_union/default: identical executable bytes and settings; timing differences are control observations, not an optimization effect
