"""Generate the independently reviewed 2,281-case float input program."""
from pathlib import Path
import random
import sys

rng = random.Random(710655582)
cases = ['', ' ', '\t\n', '+', '-', 'NaN', '-nan', '+INFINITY', 'inf_',
         '0x1.0p2', '1\x002', '1e2 suffix', '1e+', '1__0', '1._0', '_1', '1_',
         '-0.0', '-0e9999', '1e9999', '1e-9999', '\u20031.25\u2002',
         '١٢.٣e٤', '\ud800', '1.2\u001c', '1.2\u0085', '1.2\u200b']
alphabet = '0123456789eE.+-_nNaAiIfFtTyYxX \t\n\x00\u0661\u2003\ud800'
for _ in range(750):
    cases.append(''.join(rng.choice(alphabet) for _ in range(rng.randrange(0, 38))))
for _ in range(500):
    digits = ''.join(rng.choice('0123456789') for _ in range(rng.randrange(1, 65)))
    cut = rng.randrange(len(digits) + 1)
    value = (rng.choice(['', '+', '-']) + digits[:cut] + '.' + digits[cut:]
             + rng.choice(['e', 'E']) + str(rng.randrange(-450, 450)))
    cases.extend([value, ' \t' + value + '\n ', value.replace('0', '٠')])
cases.extend(['0.' + '1' * 4096, '1' + '0' * 4096, '1_' * 2048 + '2', '1e' + '9' * 4096])
source = ('from math import copysign\ncases: list[str] = [\n'
          + ''.join('    ' + ascii(x) + ',\n' for x in cases)
          + ']\nfor i in range(len(cases)):\n'
          + '    try:\n        v = float(cases[i])\n'
          + '        print(i, repr(v), copysign(1.0, v))\n'
          + '    except ValueError as e:\n        print(i, str(e))\n')
Path(sys.argv[1]).write_text(source)
print(f'Generated {len(cases)} float cases')
