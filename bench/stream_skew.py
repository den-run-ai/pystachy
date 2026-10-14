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


mode = sys.argv[1] if len(sys.argv) > 1 else "check"
repeats = int(sys.argv[2]) if len(sys.argv) > 2 else 100
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
    expected_tokens = [
        "service", "api", "--host", "localhost:8080", "--tag", "nightly build",
        "export", "ROOT=/srv/project", "NAME=two words", "EMPTY=", "run",
        "escaped value", 'quoted "word"', "https://example.test/a?q=1",
        "continue", "first\nsecond", "multiline\nvalue",
    ] * 32
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
