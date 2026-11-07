"""Use #1107's byte-BPE port in coarse, independently allocated worker heaps.

Set PYTHONPATH/PYSTACHY_PATH to the byte-BPE checkout's bench/pyperformance.
Training, I/O, process startup, encoding and decoding are all in job wall time.
"""
import sys

from bpe_tokeniser import BPE_PATTERN, SimpleBytePairEncoding


def main() -> None:
    if len(sys.argv) != 3:
        raise ValueError("expected INPUT_FILE ROUNDS")
    rounds = int(sys.argv[2])
    if rounds < 1:
        raise ValueError("rounds must be positive")
    with open(sys.argv[1]) as stream:
        data = stream.read()
    tokenizer = SimpleBytePairEncoding.train(data, 260, BPE_PATTERN)
    tokens: list[int] = []
    checksum = 0
    for _ in range(rounds):
        tokens = tokenizer.encode(data)
        decoded = tokenizer.decode(tokens)
        if decoded != data:
            raise ValueError("byte-BPE round trip changed")
        checksum += len(tokens) + len(decoded)
    print(checksum)
    print(list(tokenizer.mergeable_ranks.items()))
    print(tokens)
    print(repr(tokenizer.decode_bytes(tokens)))


if __name__ == "__main__":
    main()
