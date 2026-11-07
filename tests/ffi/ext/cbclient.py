import gc
import threading
import weakref
from array import array

import cb
import cbdata


def expect(actual, expected):
    assert actual == expected, (actual, expected)


def main():
    cb.retain()
    expect(cb.score(), 7.5)
    expect(cb.open_score(), 7.5)
    expect(cb.copied_score(), 7.5)
    expect(cb.boxed_score(), 7.5)
    cbdata.data[0] = 5.0
    expect(cb.score(), 8.5)
    try:
        cbdata.data.append(9.0)
    except BufferError:
        print("extension pins resize")
    else:
        raise AssertionError("export did not pin resize")
    ref = weakref.ref(cbdata.data)
    cbdata.data = array("d", [99.0])
    gc.collect()
    assert ref() is not None
    expect(cb.first(), 5.0)
    expect(cb.score(), 8.5)
    print("extension retains batch across calls and host reference drops")
    # The extension's existing owner-thread rule is unchanged. Source twin
    # has no such native restriction, so normalize this check in the transcript.
    errors = []

    def other_thread():
        try:
            cb.score()
        except RuntimeError as e:
            errors.append(str(e))

    t = threading.Thread(target=other_thread)
    t.start()
    t.join(10)
    assert not t.is_alive()
    if cb.__file__.endswith(".so"):
        assert len(errors) == 1 and "thread that imported" in errors[0]
    print("owner thread checked")
    cb.release()
    cb.release()
    gc.collect()
    assert ref() is None
    print("extension explicit release frees exporter")
    cbdata.data.append(100.0)
    # Repeated retained sessions do not grow a list of stale handles.
    cbdata.weights = array("d", [1.0, 1.0])
    for _ in range(50):
        cb.retain()
        expect(cb.score(), 199.0)
        cb.release()
    print("extension reuse")


main()
