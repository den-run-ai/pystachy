"""Train the educational byte tokenizer and round-trip one UTF-8 string."""
import sys

from bpe_tokeniser import BPE_PATTERN, SimpleBytePairEncoding


def main() -> int:
    if len(sys.argv) < 2 or len(sys.argv) > 4:
        print("usage: byte-bpe CORPUS [VOCAB_SIZE [TEXT]]", file=sys.stderr)
        return 2
    vocab_size = 1024
    if len(sys.argv) > 2:
        vocab_size = int(sys.argv[2])
    text = "Hello, Sebastian! Byte BPE preserves 日本語, 🦉 and\twhitespace.\n"
    if len(sys.argv) > 3:
        text = sys.argv[3]
    with open(sys.argv[1], "r", encoding="utf-8") as stream:
        training_data = stream.read()
    tokenizer = SimpleBytePairEncoding.train(training_data, vocab_size, BPE_PATTERN)
    tokens = tokenizer.encode(text)
    restored = tokenizer.decode(tokens)
    assert restored == text
    print("Vocabulary:", len(tokenizer.mergeable_ranks))
    print("UTF-8 bytes:", len(text.encode("utf-8")))
    print("Tokens:", tokens)
    print("Decoded:", repr(restored))
    print("Exact round trip:", restored == text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
