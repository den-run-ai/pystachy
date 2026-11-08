"""Shared CPython/native consumer and ownership checks for the local backend."""

import sys
from comm import Buffer, Completion, Context


def finish(ctx: Context, count: int) -> list[Completion]:
    assert ctx.progress(64) == count
    results: list[Completion] = []
    for _ in range(count):
        results.extend(ctx.poll())
    assert len(results) == count
    assert ctx.poll() == []
    return results


def collective_consumer() -> None:
    with Context() as ctx:
        inputs: list[Buffer] = []
        outputs: list[Buffer] = []
        for rank in range(4):
            source = [float(rank + 1), float(rank * rank), -float(rank)]
            inputs.append(ctx.from_f64(source))
            source[0] = 999.0  # The borrowed list must already have been copied.
            outputs.append(ctx.buffer("f64", 3))
        request = ctx.allreduce_sum(inputs, outputs, 73)
        assert not ctx.test(request)
        assert ctx.progress(0) == 0
        for source_buffer in inputs:
            source_buffer.close()  # Requests retain the native allocations.
        result = finish(ctx, 1)[0]
        assert result.request_id == request and result.tag == 73
        assert result.kind == 4 and result.status == 0
        for output in outputs:
            assert output.to_f64() == [10.0, 14.0, -6.0]
        print("allreduce", outputs[0].to_f64())

        for rank in range(4):
            outputs[rank].write_f64([float(rank + 1), float(rank * rank), -float(rank)])
        gathered: list[Buffer] = []
        for _ in range(4):
            gathered.append(ctx.buffer("f64", 12))
        request = ctx.allgather(outputs, gathered, 74)
        assert finish(ctx, 1)[0].request_id == request
        expected: list[float] = []
        for output in outputs:
            expected.extend(output.to_f64())
        for target in gathered:
            assert target.to_f64() == expected
        print("allgather", gathered[0].to_f64())

        packet = ctx.from_bytes(bytes([0, 255, 65, 0, 66]))
        peers: list[Buffer] = []
        for _ in range(3):
            peers.append(ctx.buffer("u8", 5))
        request = ctx.broadcast(packet, peers, -7)
        packet.close()
        event = finish(ctx, 1)[0]
        assert event.request_id == request and event.tag == -7 and event.kind == 2
        for peer in peers:
            assert peer.to_bytes() == bytes([0, 255, 65, 0, 66])
        print("broadcast", peers[0].to_bytes())
        byte_inputs = [ctx.from_bytes(b"a\0"), ctx.from_bytes(bytes([255, 66]))]
        byte_outputs = [ctx.buffer("u8", 4), ctx.buffer("u8", 4)]
        ctx.allgather(byte_inputs, byte_outputs)
        finish(ctx, 1)
        for byte_output in byte_outputs:
            assert byte_output.to_bytes() == bytes([97, 0, 255, 66])
        print("byte allgather", byte_outputs[0].to_bytes())


def ownership_and_views(repeat: int) -> None:
    for _ in range(repeat):
        with Context(capacity=2, byte_limit=1024) as ctx:
            source = ctx.from_bytes(bytes([0, 255, 65, 0, 66]))
            parent = ctx.from_bytes(b"...........")
            view = parent.view(3, 5)
            assert view.metadata() == [1, 5, 5, 3, 1]
            target = view.view(1, 3)
            assert target.metadata() == [1, 3, 3, 4, 1]
            target.close()
            request = ctx.copy(source, view)
            source.close()
            parent.close()
            assert finish(ctx, 1)[0].request_id == request
            assert view.to_bytes() == bytes([0, 255, 65, 0, 66])
            view.close()
            view.close()
            float_source = ctx.from_f64([99.0, 2.5, -7.0, 88.0])
            float_dest = ctx.from_f64([11.0, 12.0, 13.0, 14.0])
            source_view = float_source.view(1, 2)
            dest_view = float_dest.view(1, 2)
            assert source_view.metadata() == [2, 2, 16, 8, 1]
            ctx.copy(source_view, dest_view)
            float_source.close()
            source_view.close()
            finish(ctx, 1)
            assert float_dest.to_f64() == [11.0, 2.5, -7.0, 14.0]
            empty = ctx.buffer("f64", 0)
            dest = ctx.buffer("f64", 0)
            assert empty.metadata() == [2, 0, 0, 0, 1]
            ctx.allreduce_sum([empty], [dest])
            finish(ctx, 1)
            assert dest.to_f64() == []
    print("owned buffers, nested views, zero lengths", repeat)


def leases_and_capacity() -> None:
    with Context(capacity=1, byte_limit=64) as ctx:
        source = ctx.from_bytes(b"one")
        dest = ctx.from_bytes(b"...")
        alias = source.view(0, 3)
        spare_source = ctx.from_bytes(b"abc")
        spare_dest = ctx.buffer("u8", 3)
        request = ctx.copy(source, dest)
        rejected = False
        try:
            alias.write_bytes(b"bad")
        except RuntimeError:
            rejected = True
        assert rejected
        rejected = False
        try:
            dest.to_bytes()
        except RuntimeError:
            rejected = True
        assert rejected
        assert ctx.progress(1) == 1 and ctx.test(request)
        rejected = False
        try:
            ctx.copy(spare_source, spare_dest)
        except RuntimeError:
            rejected = True
        assert rejected  # Terminal, unconsumed requests still use capacity.
        assert ctx.poll()[0].request_id == request
        assert dest.to_bytes() == b"one"
        alias.write_bytes(b"two")
        assert source.to_bytes() == b"two"
        rejected = False
        try:
            ctx.test(request)
        except RuntimeError:
            rejected = True
        assert rejected
        newer = ctx.copy(source, dest)
        assert newer > request
        finish(ctx, 1)
        assert dest.to_bytes() == b"two"
    print("leases, terminal capacity, stale IDs")


def cancellation() -> None:
    with Context(capacity=2) as ctx:
        source = ctx.from_bytes(b"copy")
        first = ctx.from_bytes(b"1111")
        second = ctx.from_bytes(b"2222")
        earlier = ctx.copy(source, first, 10)
        later = ctx.copy(source, second, 11)
        assert ctx.cancel(later)
        assert not ctx.cancel(later)
        assert ctx.test(later) and not ctx.test(earlier)
        assert ctx.progress(64) == 1
        results = ctx.poll()
        results.extend(ctx.poll())
        assert len(results) == 2
        assert results[0].request_id == later and results[0].status == 1
        assert results[1].request_id == earlier and results[1].status == 0
        assert first.to_bytes() == b"copy" and second.to_bytes() == b"2222"
        rejected = False
        try:
            ctx.cancel(later)
        except RuntimeError:
            rejected = True
        assert rejected
    print("cancellation, completion order, no canceled writes")


def validation() -> None:
    with Context(byte_limit=64) as ctx:
        source = ctx.from_f64([1.0, 2.0])
        dest = ctx.from_f64([8.0, 9.0])
        for count in [-1, 9223372036854775807]:
            rejected = False
            try:
                ctx.buffer("f64", count)
            except (RuntimeError, ValueError, OverflowError):
                rejected = True
            assert rejected
        for offset in [-1, 3, 9223372036854775807]:
            rejected = False
            try:
                source.view(offset, 1)
            except (RuntimeError, ValueError, OverflowError):
                rejected = True
            assert rejected
        rejected = False
        try:
            ctx.copy(source, source.view(0, 2))
        except (RuntimeError, ValueError):
            rejected = True
        assert rejected
        rejected = False
        try:
            ctx.broadcast(source, [dest, dest])
        except (RuntimeError, ValueError):
            rejected = True
        assert rejected
        rejected = False
        try:
            ctx.allgather([source, source], [dest, dest])
        except (RuntimeError, ValueError):
            rejected = True
        assert rejected
        wrong = ctx.buffer("u8", 2)
        rejected = False
        try:
            ctx.copy(source, wrong)
        except (RuntimeError, ValueError):
            rejected = True
        assert rejected
        assert dest.to_f64() == [8.0, 9.0]  # All failed submissions were write-free.
        assert ctx.poll() == [] and ctx.progress(64) == 0
        with Context() as other:
            foreign = other.buffer("f64", 2)
            rejected = False
            try:
                ctx.copy(source, foreign)
            except ValueError:
                rejected = True
            assert rejected
    print("bounds, overlap, dtype, shape, context validation")


def shutdown(repeat: int) -> None:
    for _ in range(repeat):
        ctx = Context(capacity=2)
        source = ctx.from_f64([1.0, 2.0, 3.0])
        dest = ctx.buffer("f64", 3)
        ctx.copy(source, dest)
        source.close()
        ctx.close()
        ctx.close()
        rejected = False
        try:
            dest.to_f64()
        except ValueError:
            rejected = True
        assert rejected
    print("pending shutdown and idempotent close", repeat)


def main() -> None:
    repeat = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    collective_consumer()
    ownership_and_views(repeat)
    leases_and_capacity()
    cancellation()
    validation()
    shutdown(repeat)


if __name__ == "__main__":
    main()
