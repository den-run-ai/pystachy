# roman's toRoman and fromRoman: the cases of its own test suite (src/tests.py of roman 5.2),
# run as a program instead of under unittest, then the edges of both directions
import roman
import roman as rm
from roman import InvalidRomanNumeralError
from roman import NotIntegerError
from roman import OutOfRangeError
from roman import RomanError
from roman import fromRoman
from roman import toRoman
from roman import toRoman as to_roman

TEST_MAP = ((0, 'N'), (1, 'I'), (3, 'III'), (4, 'IV'), (9, 'IX'), (14, 'XIV'),
            (19, 'XIX'), (24, 'XXIV'), (40, 'XL'), (49, 'XLIX'), (90, 'XC'),
            (99, 'XCIX'), (400, 'CD'), (490, 'CDXC'), (499, 'CDXCIX'),
            (900, 'CM'), (990, 'CMXC'), (998, 'CMXCVIII'), (999, 'CMXCIX'),
            (2013, 'MMXIII'))

# test_toRoman, test_fromRoman, and the lower case of test_main_fromRoman_caseInsensitive
for num_arabic, num_roman in TEST_MAP:
    print(num_arabic, toRoman(num_arabic), fromRoman(num_roman),
          fromRoman(num_roman.lower()), toRoman(num_arabic) == num_roman)

# test_toRoman_errors (toRoman('1') is a compile-time error here) and the range's edges
for n in [100000, -1, 5000, 9223372036854775807, -9223372036854775807, -9223372036854775807 - 1]:
    try:
        print("no error", toRoman(n))
    except OutOfRangeError as e:
        print(n, "OutOfRangeError:", e)

# test_fromRoman_errors
for s in ["", "Q12"]:
    try:
        print("no error", fromRoman(s))
    except InvalidRomanNumeralError as e:
        print(repr(s), "InvalidRomanNumeralError:", e)
try:
    print("no error", fromRoman('n', special_case=False))
except InvalidRomanNumeralError as e:
    print("'n' special_case=False:", e)

# the special case, positional and by keyword
for s in ["N", "n", "N\n"]:
    for sc in [True, False]:
        try:
            print(repr(s), sc, fromRoman(s, sc), fromRoman(s, special_case=sc))
        except InvalidRomanNumeralError as e:
            print(repr(s), sc, "InvalidRomanNumeralError:", repr(str(e)))

# the exception hierarchy: every error is a RomanError
for n in [5000, 4999]:
    try:
        print(toRoman(n), toRoman(int(str(n))))
        raise NotIntegerError("decimals cannot be converted")
    except RomanError as e:
        print(type(e).__name__, isinstance(e, RomanError), isinstance(e, OutOfRangeError), e)
try:
    fromRoman("IIII")
except RomanError as e:
    print(type(e).__name__, isinstance(e, InvalidRomanNumeralError), isinstance(e, ValueError))

# every number both ways
total = 0
longest = ""
for n in range(1, 5000):
    r = roman.toRoman(n)
    if roman.fromRoman(r) != n or roman.fromRoman(r.lower()) != n:
        print("round trip mismatch", n, r)
    total += len(r)
    if len(r) > len(longest):
        longest = r
print("round trips 1..4999:", total, "characters, the longest", longest, fromRoman(longest))

# other call forms: an alias, every argument by keyword (in either order), the module's strings
# and its table as a program can use it (ports/roman/PORT.md)
print(to_roman(n=1999), rm.fromRoman(s="mcmxcix"), rm.fromRoman(special_case=True, s="n"))
try:
    rm.fromRoman(special_case=False, s="N")
except rm.InvalidRomanNumeralError as e:
    print("special_case=False first:", e)
print(rm.__author__)
print(rm.__copyright__.splitlines()[0])
print(len(rm.romanNumeralMap), rm.romanNumeralMap[1], rm.romanNumeralMap[-1][1],
      ("D", 500) in rm.romanNumeralMap)
print(list(rm.romanNumeralMap)[:3], sorted(rm.romanNumeralMap)[0])
for numeral, value in rm.romanNumeralMap:
    if fromRoman(numeral) != value or toRoman(value) != numeral:
        print("table mismatch", numeral, value)

# the error escapes as CPython reports it
toRoman(5000)
