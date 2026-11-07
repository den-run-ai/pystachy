"""Measure training, encoding and decoding separately; print complete results."""
import sys
import time

from bpe_tokeniser import BPE_PATTERN, SimpleBytePairEncoding


def main() -> None:
    if len(sys.argv) != 5:
        raise ValueError("expected CORPUS VOCAB_SIZE ENCODE_LOOPS DECODE_LOOPS")
    vocab_size = int(sys.argv[2])
    encode_loops = int(sys.argv[3])
    decode_loops = int(sys.argv[4])
    if encode_loops < 1 or decode_loops < 1:
        raise ValueError("loop counts must be positive")
    with open(sys.argv[1], "r", encoding="utf-8") as stream:
        data = stream.read()
    start = time.perf_counter()
    tokenizer = SimpleBytePairEncoding.train(data, vocab_size, BPE_PATTERN)
    train_seconds = time.perf_counter() - start
    tokens: list[int] = []
    start = time.perf_counter()
    for _ in range(encode_loops):
        tokens = tokenizer.encode(data)
    encode_seconds = time.perf_counter() - start
    decoded = ""
    start = time.perf_counter()
    for _ in range(decode_loops):
        decoded = tokenizer.decode(tokens)
    decode_seconds = time.perf_counter() - start
    # Check and expose complete state after the timed regions. The controller compares
    # every byte of this output with the pristine upstream CPython kernel's output.
    assert len(tokenizer.mergeable_ranks) == vocab_size
    assert decoded == data
    assert tokenizer.decode_bytes(tokens) == data.encode("utf-8")
    print(list(tokenizer.mergeable_ranks.items()))
    print(tokens)
    print(repr(tokenizer.decode_bytes(tokens)))
    print(repr(decoded))
    print("train", train_seconds, file=sys.stderr)
    print("encode", encode_seconds, file=sys.stderr)
    print("decode", decode_seconds, file=sys.stderr)


if __name__ == "__main__":
    main()
