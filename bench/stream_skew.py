"""Native stream-type feedback through the existing shlex character parser.

The private constructor hook preserves the stream object for this experiment.
Only read_token() is exercised; source stacking and the default shlex API keep
their existing port behavior. See docs/stream-skew.md for the CPython oracle.
"""
import sys
import time
from io import StringIO
from shlex import shlex
from typing import TextIO


DOCUMENT = (
    '# deployment settings: comments are consumed through readline\n'
    'service api --host "localhost:8080" --tag \'nightly build\'\n'
    'export ROOT=/srv/project NAME="two words" EMPTY=""\n'
    'run escaped\\ value "quoted \\"word\\"" https://example.test/a?q=1\n'
    'continue first\\\nsecond "multiline\nvalue" # trailing comment\n'
) * 32


def tokenize(stream) -> int:
    """The same parser and loop compile for erased and concrete stream types."""
    result: int = 0
    lexer = shlex(posix=True, _stream=stream)
    lexer.whitespace_split = True
    while True:
        token = lexer.read_token()
        if token is None:
            break
        result = (result * 31 + len(token) + 1) % 2147483647
    return result


def read_tokens(stream: TextIO | StringIO) -> int:
    return tokenize(stream)


def concrete(stream: StringIO) -> int:
    return tokenize(stream)


def concrete_file(stream: TextIO) -> int:
    return tokenize(stream)


def token_list(stream: TextIO | StringIO) -> list[str]:
    """Exact-content validation kept outside the timed checksum loop."""
    lexer = shlex(posix=True, _stream=stream)
    lexer.whitespace_split = True
    tokens: list[str] = []
    while True:
        token = lexer.read_token()
        if token is None:
            return tokens
        tokens.append(token)


def expected_token_list() -> list[str]:
    return [
        "service", "api", "--host", "localhost:8080", "--tag", "nightly build",
        "export", "ROOT=/srv/project", "NAME=two words", "EMPTY=", "run",
        "escaped value", 'quoted "word"', "https://example.test/a?q=1",
        "continue", "first\nsecond", "multiline\nvalue",
    ] * 32


def phase_batch(memory: StringIO, streams: list[TextIO | StringIO], path: str,
                count: int, phase: str, direct: bool) -> tuple[int, float, float]:
    """A cold prefix, memory hot phase, changed stream mix, then recovery.

    File opens/closes and memory resets are included in each phase's timing.
    process_time excludes a spawned compiler; the external harness measures
    child-inclusive CPU and the runtime reports compilation CPU separately.
    """
    start_wall = time.perf_counter()
    start_cpu = time.process_time()
    checksum: int = 0
    for i in range(count):
        use_file = False
        if phase == "cold":
            use_file = i == count - 1
        elif phase == "shift":
            half = count // 2
            use_file = i % 2 == 1 if i < half else i != count - 1
        if use_file:
            fresh = open(path)
            streams[1] = fresh
            if direct:
                checksum += concrete_file(fresh)
            else:
                checksum += read_tokens(streams[1])
            fresh.close()
        else:
            memory.seek(0)
            if direct:
                checksum += concrete(memory)
            else:
                checksum += read_tokens(streams[0])
    elapsed_cpu = time.process_time() - start_cpu
    elapsed_wall = time.perf_counter() - start_wall
    return checksum, elapsed_wall, elapsed_cpu


mode = sys.argv[1] if len(sys.argv) > 1 else "check"
repeats = int(sys.argv[2]) if len(sys.argv) > 2 else (4000 if mode in ("phases", "phases-static") else 100)
path = sys.argv[3] if len(sys.argv) > 3 else "build/stream-skew-input.txt"
with open(path, "w") as output:
    output.write(DOCUMENT)
memory = StringIO(DOCUMENT)
disk = open(path)
streams: list[TextIO | StringIO] = [memory, disk]

if mode == "train":
    result = 0
    for i in range(200):
        index = 1 if i == 199 else 0
        memory.seek(0)
        result += read_tokens(streams[index])
    print("train", result)
elif mode == "check":
    expected_tokens = expected_token_list()
    assert token_list(streams[0]) == expected_tokens
    assert token_list(streams[1]) == expected_tokens
    memory.seek(0)
    expected = concrete(memory)
    disk.close()
    disk = open(path)
    streams[1] = disk
    assert concrete_file(disk) == expected
    # Balanced, then reversed skew: the held-out stream member must stay valid.
    result = 0
    for i in range(12):
        memory.seek(0)
        disk.close()
        disk = open(path)
        streams[1] = disk
        value = read_tokens(streams[i % 2])
        assert value == expected
        result += value
    for i in range(12):
        memory.seek(0)
        disk.close()
        disk = open(path)
        streams[1] = disk
        value = read_tokens(streams[0 if i == 11 else 1])
        assert value == expected
        result += value
    print("check", expected, result)
elif mode in ("phases", "phases-static"):
    # Exact token validation does not call tokenize or prewarm its online site.
    expected_tokens = expected_token_list()
    assert token_list(streams[0]) == expected_tokens
    assert token_list(streams[1]) == expected_tokens
    expected = 586964006
    print("tokens", len(expected_tokens), expected)
    cold = int(sys.argv[4]) if len(sys.argv) > 4 else 200
    shift = int(sys.argv[5]) if len(sys.argv) > 5 else 40
    recovery = int(sys.argv[6]) if len(sys.argv) > 6 else repeats
    direct = mode == "phases-static"
    for phase, count in [("cold", cold), ("warm", repeats), ("shift", shift), ("recovery", recovery)]:
        checksum, wall, cpu = phase_batch(memory, streams, path, count, phase, direct)
        assert checksum == expected * count
        print("phase", phase, count, checksum, wall, cpu)
else:
    start = time.process_time()
    result = 0
    if mode == "static":
        for _ in range(repeats):
            memory.seek(0)
            result += concrete(memory)
    elif mode == "static-file":
        for _ in range(repeats):
            disk.close()
            disk = open(path)
            streams[1] = disk
            result += concrete_file(disk)
    elif mode == "file":
        for _ in range(repeats):
            disk.close()
            disk = open(path)
            streams[1] = disk
            result += read_tokens(streams[1])
    else:
        for _ in range(repeats):
            memory.seek(0)
            result += read_tokens(streams[0])
    elapsed = time.process_time() - start
    print(result, elapsed)

disk.close()
memory.close()
