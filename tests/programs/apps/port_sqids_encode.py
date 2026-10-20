# sqids's Sqids with its default blocklist: the cases of its own tests/test_encoding.py,
# test_minlength.py and test_alphabet.py (sqids 0.5.2), run as a program instead of under
# pytest, and numbers and ids at the edges
import sys

from sqids import Sqids
from sqids.constants import DEFAULT_ALPHABET

sqids = Sqids()

# test_encoding.py: test_simple, test_incremental_numbers, ..._same_index_0 and _1
for id_str, numbers in [
    ("86Rf07", [1, 2, 3]),
    ("bM", [0]), ("Uk", [1]), ("gb", [2]), ("Ef", [3]), ("Vq", [4]),
    ("uw", [5]), ("OI", [6]), ("AX", [7]), ("p6", [8]), ("nJ", [9]),
    ("SvIz", [0, 0]), ("n3qa", [0, 1]), ("tryF", [0, 2]), ("eg6q", [0, 3]), ("rSCF", [0, 4]),
    ("sR8x", [0, 5]), ("uY2M", [0, 6]), ("74dI", [0, 7]), ("30WX", [0, 8]), ("moxr", [0, 9]),
    ("nWqP", [1, 0]), ("tSyw", [2, 0]), ("eX68", [3, 0]), ("rxCY", [4, 0]), ("sV8a", [5, 0]),
    ("uf2K", [6, 0]), ("7Cdk", [7, 0]), ("3aWP", [8, 0]), ("m2xn", [9, 0]),
]:
    print(numbers, sqids.encode(numbers), sqids.decode(id_str) == numbers)

# test_different_inputs, test_multi_input, and numbers up to sys.maxsize
for numbers in [
    [0, 0, 0, 1, 2, 3, 100, 1_000, 100_000, 1_000_000, sys.maxsize],
    list(range(100)),
    [sys.maxsize - 1],
    [sys.maxsize, sys.maxsize, sys.maxsize],
    [2**62, 0, 2**62 + 1],
]:
    id_str = sqids.encode(numbers)
    print(len(numbers), len(id_str), id_str[:40], sqids.decode(id_str) == numbers)

# test_encoding_no_numbers, test_decoding_empty_string, test_decoding_invalid_character;
# ids that are not quite ids: a separator first, a separator only, characters outside the
# alphabet, a newline at the end
print(repr(sqids.encode([])), sqids.decode(""), sqids.decode("*"), sqids.decode("a*"))
print(sqids.decode("Ab"), sqids.decode("AAAA"), sqids.decode("été"), sqids.decode("bM\n"))
# a chunk of 11 characters, the most a 64-bit number takes: sys.maxsize's, and 10 characters
# that stand for zeros before a 7 (a 12th character raises OverflowError here, PORT.md)
print(sqids.decode("fRhxlG4QkEo5"), sqids.decode("fFFFFFFFFFF5"), sqids.encode([7]))

# test_encode_out_of_range_numbers (sys.maxsize + 1 is not an int here: 64-bit ints)
for numbers in [[-1], [sys.maxsize, -5], [1, 2, -sys.maxsize - 1]]:
    try:
        sqids.encode(numbers)
        print("no error")
    except ValueError as e:
        print("ValueError:", e)

# test_minlength.py: test_simple, test_incremental, test_incremental_numbers
for min_length in [6, 7, 8, 9, 10, 11, 12, 13, 62, 63, 64, 65]:
    s = Sqids(min_length=min_length)
    id_str = s.encode([1, 2, 3])
    print(min_length, id_str, len(id_str) == min_length, s.decode(id_str))
s = Sqids(min_length=len(DEFAULT_ALPHABET))
for id_str, numbers in [
    ("SvIzsqYMyQwI3GWgJAe17URxX8V924Co0DaTZLtFjHriEn5bPhcSkfmvOslpBu", [0, 0]),
    ("n3qafPOLKdfHpuNw3M61r95svbeJGk7aAEgYn4WlSjXURmF8IDqZBy0CT2VxQc", [0, 1]),
    ("74dID7X28VLQhBlnGmjZrec5wTA1fqpWtK4YkaoEIM9SRNiC3gUJH0OFvsPDdy", [0, 7]),
    ("moxr3HqLAK0GsTND6jowfZz3SUx7cQ8aC54Pl1RbIvFXmEJuBMYVeW9yrdOtin", [0, 9]),
]:
    print(numbers, s.encode(numbers) == id_str, s.decode(id_str))

# test_min_lengths, five of its lists, and 255, the longest minimum length
for min_length in [0, 1, 5, 10, 62, 255]:
    s = Sqids(min_length=min_length)
    for numbers in [[0], [0, 0, 0, 0, 0], list(range(1, 11)), [1000000], [sys.maxsize]]:
        id_str = s.encode(numbers)
        print(min_length, len(id_str), id_str[:16], s.decode(id_str) == numbers)

# test_out_of_range_invalid_min_length (a min_length that is not an int is a compile-time
# error here, where CPython raises TypeError)
for min_length in [-1, 256]:
    try:
        Sqids(min_length=min_length)
        print("no error")
    except ValueError as e:
        print("ValueError:", e)

# test_alphabet.py: test_simple, test_short_alphabet, test_long_alphabet, and the errors
s = Sqids(alphabet="0123456789abcdef")
print(s.encode([1, 2, 3]), s.decode("489158"))
for alphabet in [
    "abc",
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_+|{}[];:'\"/?.>,<`~",
    "\x00\x01\t\n\x7f ",
]:
    s = Sqids(alphabet=alphabet)
    for numbers in [[1, 2, 3], [4572, 0, 99], [sys.maxsize]]:
        id_str = s.encode(numbers)
        print(repr(id_str), s.decode(id_str))
s = Sqids(alphabet="abc", min_length=255)
id_str = s.encode([sys.maxsize])
print(len(id_str), id_str[:24], s.decode(id_str))
for alphabet in ["ë1092", "aabcdefg", "ab", "abcdefa", "abcé"]:
    try:
        Sqids(alphabet=alphabet)
        print("no error")
    except ValueError as e:
        print(repr(alphabet), "ValueError:", e)

# the longest alphabet, all 128 ASCII characters, and the same with one of them twice (the
# uniqueness check counts each character instead of making a set)
ascii128 = "".join(chr(i) for i in range(128))
s = Sqids(alphabet=ascii128, min_length=20)
for numbers in [[0], [1, 2, 3], [sys.maxsize, 127, 128]]:
    id_str = s.encode(numbers)
    print(len(id_str), repr(id_str[:12]), s.decode(id_str))
for alphabet in [ascii128 + "~", "\x00" + ascii128]:
    try:
        Sqids(alphabet=alphabet)
        print("no error")
    except ValueError as e:
        print(len(alphabet), "ValueError:", e)
