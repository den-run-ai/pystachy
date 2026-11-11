"""Exercise the same logging kernels with ordinary pytest fixture lifetime."""
import io
import logging
import pytest

import bm_logging


@pytest.fixture
def stream():
    output = io.StringIO()
    yield output
    output.close()


@pytest.fixture
def logger(stream):
    value = logging.getLogger("pytest-pyperformance")
    value.propagate = False
    value.setLevel(logging.WARNING)
    handler = logging.StreamHandler(stream=stream)
    value.addHandler(handler)
    yield value
    value.removeHandler(handler)
    handler.close()


def test_logging(logger, stream):
    bm_logging.bench_silent(1, logger, stream)
    assert stream.getvalue() == ""
    bm_logging.bench_simple_output(1, logger, stream)
    assert stream.getvalue() == (bm_logging.MESSAGE + "\n") * 10
    bm_logging.bench_formatted_output(1, logger, stream)
    assert stream.getvalue() == (bm_logging.FORMAT % bm_logging.MESSAGE + "\n") * 10
