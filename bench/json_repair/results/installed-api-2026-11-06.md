# Installed JSON repair API: 2026-11-06

This campaign measures the installed `pystachy_json_repair` public API, including
Python/native conversion, on constructed records. It compares pristine upstream
`json_repair` v0.64.1, the adapted port on the same CPython, and the native companion.
It does not measure an entire AI application or a production distribution.

For the 80/20 mixture in the ordinary request loop, installed text, object and log
calls are respectively **4.31×, 4.38× and 3.56×** faster than pristine upstream,
and **3.33×, 2.88× and 2.40×** faster than the adapted Python baseline. Resident
memory after 80,000 calls in the request loop is **51.5–52.2 MiB** for the companion versus
**19.7–20.3 MiB** for upstream Python. These measurements support further use in
persistent Python workers, with the higher memory footprint and platform/thread
contract included in deployment decisions. Sample ranges below retain host noise.

## Source and machine

- Benchmark/source checkout: `b06af44a5916b47b1c7e0d30da7e2b12d06d1a11`; clean before and after the campaign.
- Wheel build checkout: `c5c2effe0c92dd2c02dc838c8caccd361dd521dc`. The later benchmark commit changes the harness, its tests and documentation; compiler, runtime, port and companion sources are unchanged.
- Pristine upstream: `ace9b23cb7fc6757775d5fafbfaaa9a88363a573`; all pinned source hashes verified.
- Python: `3.13.16 (main, Oct 14 2026, 01:04:01) [Clang 23.1.3 ]`.
- CPU: AMD EPYC 9V74 80-Core Processor; affinity `[0]`.
- Platform: `Linux-6.18.57-x86_64-with-glibc2.39`.
- Native build: LLVM/Clang 18.1.3, Linux x86-64, glibc 2.39. The ELF symbol floor is glibc 2.38; this is a local Linux wheel, without a manylinux certification.
- Wheel SHA-256: `13561e9d88f9ad6b31ab2d9ca8077c36041abb0c4f1cb169b3a4d7a447779976`.

The VM is shared with other sessions. All native builds and tests owned by this task
finished before timing, but CPU pinning does not reserve the VM or remove host noise.

## Method and correctness

Eight record shapes appear in each all-valid/all-malformed control. The mixed workload
contains 80% valid and 20% malformed requests by count, with every shape represented.
Text means `repair_json(ensure_ascii=False)`; objects means `loads()`; logs means
`loads(logging=True)`. Valid object/log requests use the companion’s CPython decoder;
malformed requests include native repair and CPython decoding of returned JSON payloads.

Each configuration has three fresh isolated workers, with backend order rotated across
the three pairs. Each worker calibrates toward 200 ms per batch, runs two warmup batches
and three measured batches. Tables give the median of the three process medians per
request. Ratios divide those reported medians. Calibration, startup, input construction
and complete-result validation are outside the steady timer; public API calls, result
lists, request-loop overhead and a length checksum are inside it.

Calibration outcomes: `{'target_reached': 162}`. Across all 486 measured batches, durations ranged
from 0.148 to 0.399 seconds, with median 0.220 seconds.
The target is a calibration aid, not a post-measurement filter; every sample is retained.

All three backends matched 135 benchmark-specific tagged witnesses before timing.
Tags distinguish types, signed zero, dictionary order, code points, logs and errors.
Workers compare complete final outputs with their initial values and the pristine
witnesses; intermediate calls receive a length checksum. This is separate from the
larger 837-case compatibility replay. Sources, Python, harness and installed binaries
remain fingerprinted and stable across the campaign.

## Ordinary request loop (group size 1)

| API | Inputs | Upstream CPython (µs) | Adapted CPython (µs) | Installed companion (µs) | Upstream / installed | Adapted / installed |
|---|---|---:|---:|---:|---:|---:|
| text | valid | 6.07 | 5.72 | 3.78 | 1.61× | 1.52× |
| text | malformed | 96.61 | 61.79 | 12.84 | 7.52× | 4.81× |
| text | mixed | 25.02 | 19.34 | 5.80 | 4.31× | 3.33× |
| objects | valid | 2.69 | 2.38 | 1.72 | 1.56× | 1.38× |
| objects | malformed | 86.56 | 54.31 | 14.83 | 5.84× | 3.66× |
| objects | mixed | 21.39 | 14.09 | 4.88 | 4.38× | 2.88× |
| logs | valid | 2.80 | 2.41 | 1.74 | 1.60× | 1.38× |
| logs | malformed | 93.40 | 57.89 | 22.55 | 4.14× | 2.57× |
| logs | mixed | 21.71 | 14.67 | 6.11 | 3.56× | 2.40× |

These ratios combine the existing parser adaptations, execution and Python facade.
The adapted baseline separates some of those contributions; neither ratio is a pure
compiler-only measurement. In particular, valid object/log requests stay in CPython.

## Grouped ordinary calls (maximum group size 32)

| API | Inputs | Upstream CPython (µs) | Adapted CPython (µs) | Installed companion (µs) | Upstream / installed | Adapted / installed |
|---|---|---:|---:|---:|---:|---:|
| text | valid | 5.48 | 5.20 | 3.35 | 1.64× | 1.55× |
| text | malformed | 98.63 | 62.21 | 12.67 | 7.79× | 4.91× |
| text | mixed | 25.75 | 18.09 | 5.19 | 4.96× | 3.49× |
| objects | valid | 2.32 | 2.16 | 1.48 | 1.57× | 1.46× |
| objects | malformed | 95.67 | 51.79 | 15.95 | 6.00× | 3.25× |
| objects | mixed | 20.76 | 12.98 | 4.42 | 4.70× | 2.94× |
| logs | valid | 2.35 | 2.16 | 1.42 | 1.66× | 1.52× |
| logs | malformed | 97.55 | 56.02 | 21.36 | 4.57× | 2.62× |
| logs | mixed | 22.30 | 14.72 | 5.64 | 3.95× | 2.61× |

Grouping still makes one public API call per input. It is not a native bulk API.
The eight-record controls fit in one group; the forty-record mixture uses two groups.

## Timing variation

Ranges below are the minimum and maximum of the three fresh-process medians for
group size 1, in microseconds per request. They are not confidence intervals.

| API | Inputs | Upstream range | Adapted range | Installed range |
|---|---|---:|---:|---:|
| text | valid | 5.56–6.52 | 5.56–5.91 | 3.50–4.12 |
| text | malformed | 92.57–98.29 | 57.97–63.46 | 12.84–13.23 |
| text | mixed | 23.40–25.02 | 17.38–19.47 | 5.48–6.95 |
| objects | valid | 2.54–2.75 | 2.34–2.59 | 1.68–1.86 |
| objects | malformed | 86.37–125.64 | 53.95–56.19 | 14.64–16.14 |
| objects | mixed | 19.67–23.93 | 12.84–14.62 | 4.34–5.25 |
| logs | valid | 2.69–2.82 | 2.40–3.69 | 1.74–1.91 |
| logs | malformed | 89.10–94.41 | 56.07–59.64 | 21.72–28.10 |
| logs | mixed | 21.36–23.14 | 14.40–15.71 | 5.91–6.24 |

## Fresh-process startup

Each cell is the median of three fresh workers. Import and the first malformed request
are timed separately. Worker wall time also includes Python launch, common harness
setup and reporting; it is not a bare application-import or CLI-startup measurement.
Compilation and installation are excluded.

| API | Backend | Backend import (ms) | First malformed call (ms) | Whole worker (ms) |
|---|---|---:|---:|---:|
| text | upstream | 12.570 | 0.422 | 59.693 |
| text | adapted | 11.721 | 0.263 | 58.683 |
| text | installed | 1.102 | 0.104 | 48.253 |
| objects | upstream | 12.410 | 0.269 | 54.641 |
| objects | adapted | 11.003 | 0.257 | 53.596 |
| objects | installed | 0.853 | 0.084 | 40.400 |
| logs | upstream | 12.885 | 0.343 | 54.624 |
| logs | adapted | 11.061 | 0.221 | 51.187 |
| logs | installed | 0.830 | 0.129 | 40.236 |

## Sustained requests and resident memory

One fresh worker per backend/API processes the 80/20 mixture: 20,000 warmup requests,
then three blocks of 20,000, totaling 80,000 calls in the request loop. Each worker
also makes 40 initial calls to establish expected values. Results retained by the harness
are bounded to expected/latest workload values and the current group. CPython GC runs
before snapshots; native GC is not forced. Linux values use `/proc/self/status`
`VmRSS` and `VmHWM`, scoped to the current address space since exec.
These readings include interpreter, native heap and allocator retention. They do not
measure native live objects or prove leak freedom.

| API | Backend | RSS after warmup (MiB) | RSS after request loop (MiB) | Final high-water (MiB) |
|---|---|---:|---:|---:|
| text | upstream | 19.64 | 19.66 | 19.66 |
| text | adapted | 19.57 | 19.59 | 19.59 |
| text | installed | 51.52 | 51.53 | 51.53 |
| objects | upstream | 19.82 | 19.86 | 19.86 |
| objects | adapted | 19.66 | 19.69 | 19.69 |
| objects | installed | 50.46 | 51.66 | 51.66 |
| logs | upstream | 20.26 | 20.31 | 20.31 |
| logs | adapted | 19.88 | 19.93 | 19.93 |
| logs | installed | 51.64 | 52.20 | 52.20 |

## Wheel validation and remaining boundaries

The same `0.1.0.dev3` Linux x86-64 wheel passed isolated installation on CPython
3.12.14 and 3.13.16. Each interpreter passed all 837 replay cases normally and with forced
native GC, the additional multilingual strict-error probes, 20 CLI cases, two
independently spawned process workers and two rejected foreign-thread entries.

Only the importing thread may enter the native extension and calls hold the GIL.
Object/log results still cross as JSON text. The builder supports host-native aarch64
tagging, but no ARM execution result is claimed here. macOS, cross-compilation,
free-threaded CPython and portable multi-platform distribution remain outside this
validated wheel. Case mapping remains separate from the five corrected Unicode predicates.

Core validation includes all 837 cases under pristine/adapted CPython, native JIT/AOT
and both native GC-stress modes; all-code-point classification checks; compiler and
runtime bootstrap fixed points; fast checks, lint, all 2,144 CPython recordings, runtime
contracts, and IR validity/effect checks for 2,360 programs. The strict comparison
against main reports 261/4,240 differences, exhaustively classified as compiler-home
paths/literals. It exits 1; no instruction, acceptance/rejection or exit-status change
was found. Full `make verify` or the required CI matrix is still a merge gate.

## Retained evidence and reproduction

- [Calibrated raw JSON, losslessly gzip-compressed](installed-api-2026-11-06.json.gz). Uncompressed SHA-256: `62846b11d80141d3680dbae6def05c605a8cf15a0485a3f0ca73c5b2da0fac80`.
- [Initial short-sample run](installed-api-short-2026-11-06.json.gz). It used fixed 100-round samples and the old `getrusage` peak counter. Its noisy timings and inherited pre-exec peaks are retained for transparency; the tables above use the calibrated, corrected campaign.
- [Build/ELF audit and CPython 3.13 installation check](installed-wheel-2026-11-06.json).
- [CPython 3.12 installation check](installed-wheel-cpython312-2026-11-06.json).

Run the wheel’s interpreter with a pristine pinned upstream checkout and a clean
Pystachy checkout. Use an available CPU for your environment:

```sh
/path/to/venv/bin/python tools/json_repair_api_bench.py \
  --upstream /path/to/json_repair_upstream --adapted /path/to/pystachy \
  --cpu 0 --pairs 3 --batches 3 --warmups 2 --rounds 100 \
  --min-sample-seconds 0.2 --group-sizes 1 32 --memory-rounds 500 \
  --output /tmp/json-repair-api.json
```
