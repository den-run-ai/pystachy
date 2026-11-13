# Float rounding without libm (branch claude/dreamy-shannon-bb3cu1-float-rounding)

Against main `5f81cc25`, same host as the parent directory, programs built AOT by the branch's
hosted compiler with and without its `runtime.c` change; outputs are identical.

libm calls through the PLT ([countlibm2.c](countlibm2.c), LD_PRELOAD) of `bench/*.py` and
`bench/pyperformance/*.py` built by the runtime PR stack (#1436, #1437, #1442): [counts.txt](counts.txt).
Most make none; regex_dna makes 800,000 `fmod` calls from `seed = (seed * 3877.0 + 29573.0) % 139968.0`,
chaos 53,991 `pow` (`x ** 2`) and 12,995 `trunc` (#1437's inline exact path, since moved out of line),
nbody 200,030 `pow`; go's `log` and float's `sin`/`cos` are the work itself.

Paired medians of pinned, rotated rounds ([time_variants.py](../prs/time_variants.py)):

| Program | main | branch | paired ratio |
|---|---:|---:|---:|
| [round_loop.py](round_loop.py) 10M (`math.floor`, `round`, `math.ceil`, `math.trunc`) | 0.127 s | 0.079 s | 0.642 (7/7) ([json](t_round2.json)) |
| [fmod_loop.py](fmod_loop.py) 10M (whole `%`, then fractional `//` and `%`) | 0.180 s | 0.160 s | 0.918 (7/7) ([json](t_fmod2.json)) |
| pyperformance regex_dna | 0.070 s | 0.070 s | 1.054 (1/5): no change ([json](t_regex.json)) |

Those are of `4a148105`; the first commit, `23900063`, gave 0.691 and 0.974
([t_round.json](t_round.json), [t_fmod.json](t_fmod.json)): one out-of-line path served both `%` and
`//`, so a fractional `%` also computed the quotient's `floor()`.

At 1M iterations, round_loop's libm calls fall from 4,500,000 to 247,500 (its fractional `%`
keeps `fmod`), and fmod_loop's from 1,749,993 to 749,993 (the fractional loop keeps `fmod` and
`//`'s `floor`). A 32-bit division costs about
what glibc's `fmod` does at these magnitudes, so whole `%` gains little.
