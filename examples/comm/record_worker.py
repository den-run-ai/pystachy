"""Persistent completion-record consumer shared by CPython and native Pystachy.

The pipe transports bounded ASCII JSON lines. The local backend owns and copies
each record before acknowledging it; it does not itself communicate with peers.
"""

import sys
from comm import Context


def transfer_record(ctx: Context, record: bytes, tag: int) -> bytes:
    if len(record) > 4096:
        raise ValueError("completion record exceeds 4096 bytes")
    source = ctx.from_bytes(record)
    try:
        destination = ctx.buffer("u8", len(record))
        try:
            request = ctx.copy(source, destination, tag)
            source.close()  # The accepted request now owns the input lifetime.
            progressed = ctx.progress(1)
            if progressed != 1:
                raise RuntimeError("record copy did not progress")
            event = ctx.peek()
            if event is None:
                raise RuntimeError("record copy has no completion")
            if event.request_id != request or event.tag != tag or event.status != 0 or event.kind != 1:
                raise RuntimeError("unexpected record completion")
            ctx.ack(request)
            result = destination.to_bytes()
            if result != record:
                raise RuntimeError("record copy changed the payload")
            return result
        finally:
            destination.close()
    finally:
        source.close()


def read_record() -> str:
    # Pystachy's current readline() omits CPython's size argument. Bounded
    # read(1) preserves the input limit under both implementations.
    line = ""
    for _ in range(4097):
        char = sys.stdin.read(1)
        if char == "":
            if line != "":
                raise ValueError("unterminated completion record")
            return ""
        line += char
        if char == "\n":
            if len(line) > 4096:
                raise ValueError("oversized completion record")
            return line
    raise ValueError("oversized completion record")


def main() -> None:
    with Context(capacity=1, byte_limit=8192) as ctx:
        tag = 0
        while True:
            # ASCII JSON has the same character/byte bound on every interpreter.
            line = read_record()
            if line == "":
                break
            if not line.endswith("\n"):
                raise ValueError("unterminated or oversized completion record")
            record = line.encode("ascii")
            result = transfer_record(ctx, record, tag)
            sys.stdout.write(result.decode("ascii"))
            sys.stdout.flush()
            tag += 1


if __name__ == "__main__":
    main()
