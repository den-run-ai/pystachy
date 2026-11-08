"""Portable numerical/boundary probes for the local completion contract."""

from comm import Buffer, Context


def reduce_scalar(values: list[float]) -> float:
    with Context() as ctx:
        inputs: list[Buffer] = []
        outputs: list[Buffer] = []
        for value in values:
            inputs.append(ctx.from_f64([value]))
            outputs.append(ctx.buffer("f64", 1))
        request = ctx.allreduce_sum(inputs, outputs)
        completed = ctx.progress()
        assert completed == 1
        event = ctx.peek()
        assert event is not None and event.request_id == request and event.status == 0
        ctx.ack(request)
        result = outputs[0].to_f64()[0]
        for output in outputs[1:]:
            actual = output.to_f64()[0]
            assert actual == result or (actual != actual and result != result)
        return result


def main() -> None:
    # The API specifies ordinary IEEE additions in source-list order, rather
    # than CPython 3.12+'s compensated sum() algorithm.
    first = reduce_scalar([1e16, 1.0, -1e16])
    second = reduce_scalar([1e16, -1e16, 1.0])
    assert first == 0.0 and second == 1.0
    print("source-order sums", first, second)
    infinity = float("inf")
    nan_result = reduce_scalar([infinity, -infinity])
    assert nan_result != nan_result
    assert reduce_scalar([infinity, 1.0]) == infinity
    print("nonfinite IEEE results")

    with Context(capacity=1, byte_limit=64) as ctx:
        source = ctx.from_bytes(b"owned")
        destination = ctx.buffer("u8", 5)
        bad = ctx.buffer("f64", 1)
        rejected = False
        try:
            ctx.copy(source, bad)
        except RuntimeError:
            rejected = True
        assert rejected
        # Failed submission must not hold capacity or leases.
        source.write_bytes(b"fresh")
        request = ctx.copy(source, destination, int("9223372036854775807"))
        rejected = False
        try:
            ctx.ack(request)
        except RuntimeError:
            rejected = True
        assert rejected and not ctx.test(request)
        cancelled = ctx.cancel(request)
        assert cancelled and ctx.test(request)
        event = ctx.peek()
        assert event is not None and event.tag == int("9223372036854775807")
        assert event.status == 1
        rejected = False
        try:
            destination.to_bytes()
        except RuntimeError:
            rejected = True
        assert rejected
        ctx.ack(request)
        assert destination.to_bytes() == b"\0\0\0\0\0"
        source.write_bytes(b"again")
        request = ctx.copy(source, destination, -int("9223372036854775807") - 1)
        completed = ctx.progress()
        assert completed == 1
        event = ctx.peek()
        assert event is not None and event.tag == -int("9223372036854775807") - 1
        ctx.ack(request)
        assert destination.to_bytes() == b"again"
    print("signed tag limits, failed-submit atomicity, cancellation leases")


if __name__ == "__main__":
    main()
