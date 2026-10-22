"""Semantic Str layout checks shared by rt-abi and its mutation tests."""
import re


# Appended only to the ABI check's C input. Clang folds offsetof/sizeof into LLVM
# constants, so checking a cross target needs no execution or object-layout guess.
STR_PROBE = """
#include <stddef.h>
const uint64_t pystachy_abi_str_len = offsetof(Str, len);
const uint64_t pystachy_abi_str_dict_hash = offsetof(Str, dict_hash);
const uint64_t pystachy_abi_str_chars1 = offsetof(Str, chars1);
const uint64_t pystachy_abi_str_s = offsetof(Str, s);
const uint64_t pystachy_abi_str_size = sizeof(Str);
"""
STR_FIELDS = ("len", "dict_hash", "chars1", "s", "size")
LITERAL = re.compile(
    r'^(@[sb]\.\d+) = private unnamed_addr global '
    r'\{i64, i64, i64, \[(\d+) x i8\]\} '
    r'\{i64 (\d+), i64 (\d+), i64 (\d+), \[(\d+) x i8\] c"(.*)"\}, align 8$'
)


def str_offsets(ir):
    offsets = {}
    for name in STR_FIELDS:
        match = re.search(rf"^@pystachy_abi_str_{name} = .*constant i64 (\d+)(?:,|$)", ir, re.M)
        if match:
            offsets[name] = int(match.group(1))
    return offsets


def str_offset_errors(offsets, header_size):
    expected = {"len": 0, "dict_hash": 8, "chars1": 16, "s": header_size, "size": header_size}
    return [f"Str.{name}: C offset/size {offsets.get(name)!r}, compiler {want}"
            for name, want in expected.items() if offsets.get(name) != want]


def llvm_bytes(text):
    result = bytearray()
    at = 0
    while at < len(text):
        if text[at] == "\\":
            escape = text[at + 1:at + 3]
            if len(escape) != 2 or any(c not in "0123456789abcdefABCDEF" for c in escape):
                raise ValueError("invalid LLVM byte escape")
            result.append(int(escape, 16))
            at += 3
        else:
            result.append(ord(text[at]))
            at += 1
    return bytes(result)


def str_literal_errors(ir):
    errors = []
    count = 0
    for line in ir.splitlines():
        if not re.match(r"^@[sb]\.\d+ =", line):
            continue
        count += 1
        match = LITERAL.fullmatch(line)
        if not match:
            errors.append("malformed Str literal: " + line.split(" =", 1)[0])
            continue
        name, declared, length, hash_, chars1, initialized, text = match.groups()
        try:
            data = llvm_bytes(text)
        except ValueError as error:
            errors.append(f"{name}: {error}")
            continue
        if not data or data[-1] != 0 or int(declared) != len(data) or int(initialized) != len(data):
            errors.append(f"{name}: Str byte length or trailing NUL differs")
        expected = (len(data) - 1, 0, len(data) if data.isascii() else 0)
        actual = (int(length), int(hash_), int(chars1))
        if actual != expected:
            errors.append(f"{name}: Str (len, dict_hash, chars1) {actual}, expected {expected}")
    if not count:
        errors.append("no Str literals checked")
    return errors
