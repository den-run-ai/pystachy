# The optional bounded parser and baseline must match pinned CPython, including
# rejected suffixes, underscores, Unicode normalization and signed zero.
import math

texts = [
    "0", "-0", "+0.0", "-0e-9999", "1", "  +12.5", "12.5 \t\r\n",
    "1_234.5_6e+0_2", "0_0.0", "1." , ".5", "1e2", "1.e-2", "3.141592653589793",
    "1e309", "-1e309", "1e-9999", "-1e-9999", "5e-324", "2.2250738585072014e-308",
    "InF", "-iNfInItY", "+NaN", "-nan", "  infinity  ", "nan\t", "\u2003١٢.٣٤\u3000",
    "１２３.４５", "١_٢.٣_٤e+٢", "", " ", "+", "-", ".", "+.", "1e", "1e+",
    "1e-", "1ee2", "1e+e2", "1.2.3", "1_", "_1", "1__2", "1_.2", "1._2",
    "1_e2", "1e_2", "1e+_2", "nan(payload)", "infinite", "0x1p0", "1\x00",
    "1\x002", "1 2", "1 \t2", "1\n2", "1\u20032", "١\x002", "١_", "1\u001c",
    "\u001c1", "1\u00b2", "\u22121", "1" + "_0" * 512, "0." + "0" * 512 + "1",
    "9" * 512 + " 2", "9" * 512 + " \t", "nan" + " " * 128,
]
for text in texts:
    try:
        value = float(text)
        print(repr(text), repr(value), math.copysign(1.0, value))
    except ValueError:
        print(repr(text), "ValueError")
