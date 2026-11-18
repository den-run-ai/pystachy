# Unicode case method costs

`str`'s nine case methods run an ASCII loop first and follow CPython's per-character
algorithms only for a string with a byte that is not ASCII (see
[Unicode case](../../docs/runtime-in-subset.md#unicode-case)). These two programs measure
what that costs ASCII text and how the per-character path compares with CPython. Both
run unchanged under CPython, whose output is the expected one.

- `opbench.py METHOD REPS COPIES TEXT` calls one method `REPS` times on `TEXT` and a
  space, repeated `COPIES` times. It tests each result without counting its characters.
- `casebench.py long REPS TEXT` calls all nine methods on `TEXT` and a space, repeated
  2,000 times. `casebench.py short REPS TEXT` calls `lower`, `upper`, `islower` and
  `title` on each word of `TEXT`.

```sh
text="Съешь же ещё этих мягких французских булок да выпей чаю"
python3.13 bench/unicode_case/opbench.py lower 2000 2000 "$text"
./pystachy build bench/unicode_case/opbench.py -o /tmp/opbench
/tmp/opbench lower 2000 2000 "$text"
valgrind --tool=callgrind --callgrind-out-file=/dev/null /tmp/opbench lower 100 2000 "$text"
```

Compare each output with CPython's before counting or timing. Callgrind's instruction
count (`Ir`) repeats exactly, so it can compare two compilers on a shared host. Wall
times need several samples, alternating between the programs on one core.

## Results

On 2026-11-17, parent `71e14a88` (main) and candidate `e9d4347f` built the programs as
AOT executables at the default optimization, each with its own CPython-hosted compiler
and a private runtime cache, on x86-64 Linux with LLVM 18.1.3 and CPython 3.13.16.
Every output matched CPython's.
[The results file](results/2026-11-17-linux-x86_64.json) has the arguments, every
sample and the hashes of the sources.

### ASCII text

The counts are instructions of the whole process, which include startup and building
the text. The mixed-case text is
`The Quick Brown Fox Jumps Over The Lazy Dog and KEEPS running`; the other texts are
its lower-case, upper-case and titled forms.

| Program and arguments | Text | Parent | Candidate | Change |
|---|---|---:|---:|---:|
| `bench/words.py` | its own | 484,645,369 | 494,016,211 | +1.9% |
| `casebench.py short 20000` | mixed case | 140,751,499 | 160,672,002 | +14.2% |
| `casebench.py long 20` | mixed case | 139,717,345 | 142,901,210 | +2.3% |
| `opbench.py lower 100 2000` | mixed case | 88,912,100 | 91,247,871 | +2.6% |
| `opbench.py upper 100 2000` | mixed case | 88,916,600 | 91,251,871 | +2.6% |
| `opbench.py swapcase 100 2000` | mixed case | 89,697,979 | 92,033,328 | +2.6% |
| `opbench.py casefold 100 2000` | mixed case | 88,924,079 | 91,259,628 | +2.6% |
| `opbench.py title 100 2000` | mixed case | 223,083,600 | 227,352,539 | +1.9% |
| `opbench.py capitalize 100 2000` | mixed case | 88,674,489 | 91,004,186 | +2.6% |
| `opbench.py islower 100 2000` | lower case | 137,108,983 | 128,978,416 | −5.9% |
| `opbench.py isupper 100 2000` | upper case | 137,104,783 | 141,373,516 | +3.1% |
| `opbench.py istitle 100 2000` | titled | 189,509,783 | 177,116,216 | −6.5% |
| `opbench.py isupper 100 2000` | lower case | 705,232 | 709,665 | +0.6% |

The short mode makes 960,000 calls on words of three to seven letters, so the
candidate adds about 21 instructions to each call. On strings of 124,000 characters
the methods take 1.9% to 3.1% more instructions, except `islower` and `istitle`, which
take about 6% fewer. In the last row the first letter decides the result.

Hello world, which calls no case method, stays at 93,976 bytes. The executable of
`bench/words.py` grows by 16,824 bytes, of `opbench.py` by 17,128 and of
`casebench.py` by 25,224.

### Text that is not ASCII

The times are seconds of the whole process for `opbench.py METHOD 2000 2000 TEXT`,
the candidate's executable against CPython: the median of five samples that alternate
on one core, with the lowest and the highest. The Russian text above gives 112,000
characters, 46 of each 56 not ASCII. The French text gives 120,000 characters, 11 of
each 60 not ASCII:

```text
Élan vital à l'école élémentaire où ça coûte très cher déjà
```

The three predicates read the lower-case, upper-case and titled form of each text, so
that both implementations test every character.

| Text | Method | Executable | CPython | Executable / CPython |
|---|---|---:|---:|---:|
| Russian | `lower` | 2.52 (2.25–2.63) | 0.59 (0.48–0.65) | 4.3 |
| Russian | `upper` | 3.15 (2.96–3.60) | 0.57 (0.49–0.65) | 5.6 |
| Russian | `swapcase` | 4.99 (4.83–5.05) | 1.15 (1.09–1.33) | 4.3 |
| Russian | `casefold` | 2.62 (2.28–2.82) | 0.63 (0.57–0.68) | 4.2 |
| Russian | `title` | 4.36 (4.24–4.44) | 1.21 (1.03–1.53) | 3.6 |
| Russian | `capitalize` | 2.54 (2.22–2.60) | 0.54 (0.46–0.68) | 4.7 |
| Russian, lower case | `islower` | 3.58 (3.47–3.62) | 0.61 (0.48–0.71) | 5.9 |
| Russian, upper case | `isupper` | 3.47 (3.33–3.63) | 0.72 (0.48–0.91) | 4.8 |
| Russian, titled | `istitle` | 3.74 (3.67–3.94) | 0.94 (0.88–0.96) | 4.0 |
| French | `lower` | 1.18 (1.04–1.36) | 0.61 (0.50–0.82) | 1.9 |
| French | `upper` | 1.23 (1.20–1.44) | 0.59 (0.53–0.62) | 2.1 |
| French | `swapcase` | 1.79 (1.65–1.86) | 1.30 (1.19–1.37) | 1.4 |
| French | `casefold` | 1.06 (0.86–1.11) | 0.57 (0.46–0.67) | 1.9 |
| French | `title` | 1.56 (1.40–1.67) | 1.14 (0.97–1.26) | 1.4 |
| French | `capitalize` | 1.16 (0.97–1.21) | 0.61 (0.44–0.67) | 1.9 |
| French, lower case | `islower` | 1.46 (1.19–1.59) | 0.69 (0.57–0.71) | 2.1 |
| French, upper case | `isupper` | 1.58 (1.30–1.85) | 0.64 (0.58–0.66) | 2.5 |
| French, titled | `istitle` | 1.45 (1.28–1.58) | 0.95 (0.85–1.12) | 1.5 |

The executable takes 3.6 to 5.9 times CPython's time on the Cyrillic text and 1.4 to
2.5 times on the French one. Each character that is not ASCII takes at least one
binary search of the generated tables, where CPython reads a two-stage index. With no
repetitions a run takes 0.002 s as an executable and 0.013 s under CPython.

The ratios are approximate. The host is shared, and a sample differs from its median by
up to 35%. This CPython was built from source at `-O3` without profile-guided
optimization, so a distribution's build may be faster. JIT, other architectures and
other operating systems were not measured.
