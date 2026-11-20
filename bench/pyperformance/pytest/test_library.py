"""Library kernels: encodings, listings, formatted text, decompressed and encrypted data."""
import hashlib
import os
import shutil

import bm_base64
import bm_pathlib
import bm_pprint
import crypto_pyaes
import pyflate


def test_base64():
    assert len(bm_base64.DATA_HUGE) == 1048574
    assert hashlib.md5(bm_base64.DATA_SMALL).hexdigest() == "48a56760bacbf02e0ed60c046f22a1f2"
    assert hashlib.md5(bm_base64.B64_HUGE).hexdigest() == "9eb979f1f5d34e9c5277746b294fa0bc"
    assert hashlib.md5(bm_base64.A85_LARGE).hexdigest() == "bcb3a42fec6752ff300ebb68f3f67d51"
    assert bm_base64.base64.b32decode(bm_base64.B32_MEDIUM) == bm_base64.DATA_MEDIUM
    assert bm_base64.base64.b85decode(bm_base64.B85_9K_STR) == bm_base64.DATA_9K
    before = len(bm_base64.TIMED)
    bm_base64.bench_b64_small(1)
    bm_base64.bench_urlsafe_b64_small(1)
    bm_base64.bench_b16_small(1)
    assert len(bm_base64.TIMED) == before + 3


def test_pathlib():
    tmp_path = bm_pathlib.setup(bm_pathlib.NUM_FILES)
    try:
        names, matches = bm_pathlib.bench_pathlib(1, tmp_path)
    finally:
        shutil.rmtree(tmp_path)
    assert not os.path.exists(tmp_path)
    assert (len(names), names[0], names[-1]) == (2000, "1.py", "999.tar.gz")
    assert (len(matches), matches[0], matches[-1]) == (500, "1.py", "997.py")


def test_pprint():
    data = bm_pprint.printable[:3]
    row = "('string', (1, 2), [3, 4], {5: 6, 7: 8})"
    assert bm_pprint.p.pformat(data) == "[" + row + ",\n " + row + ",\n " + row + "]"
    assert bm_pprint.p._safe_repr(data, {}, None, 0) == ("[" + row + ", " + row + ", " + row + "]", True, False)
    assert len(bm_pprint.printable) == 100000


def test_pyflate():
    out = pyflate.bench_pyflake(1, "bench/pyperformance/data/interpreter.tar.bz2")
    assert len(out) == 399360
    assert hashlib.md5(out).hexdigest() == "afa004a630fe072901b1d9628b960974"
    assert len(pyflate.TIMED) == 1


def test_crypto_pyaes():
    ciphertext = crypto_pyaes.bench_pyaes(1)
    assert len(ciphertext) == len(crypto_pyaes.CLEARTEXT) == 23000
    assert hashlib.md5(ciphertext).hexdigest() == "730a31abcccb1d0491a2a73360383cce"
    assert crypto_pyaes.pyaes.AESModeOfOperationCTR(crypto_pyaes.KEY).decrypt(ciphertext) == crypto_pyaes.CLEARTEXT
