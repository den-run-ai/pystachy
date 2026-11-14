"""librt.base64 as Pystachy compiles it: Base64 for mypy's inter-process messages.

The API of librt 0.16.0's base64 module, whose results, checks and errors follow its C source
(base64/librt_base64.c, Copyright (c) 2025 Mypyc contributors, MIT License; see
THIRD_PARTY_NOTICES), in the subset, on binascii. The encoders take a bytes. The decoders take a
bytes or a str of ASCII characters and decode what base64.b64decode() decodes: characters outside
the alphabet are ignored, and so is padding that is not at the end. Their errors are the C
module's, not base64's: ValueError("Incorrect padding") where the padding does not complete the
last four characters, and RuntimeError("base64_decode failed") where one character and three
padding characters end the data.
"""
import binascii

_TO_URLSAFE = bytes.maketrans(b"+/", b"-_")
_FROM_URLSAFE = bytes.maketrans(b"-_", b"+/")


def _digit(c: int) -> bool:
    # is_valid_base64_char() without padding: a character of the standard alphabet
    return 65 <= c <= 90 or 97 <= c <= 122 or 48 <= c <= 57 or c == 43 or c == 47


def _wellformed(data: bytes) -> bool:
    # what the C module's decoder (base64_decode() of its base64 library) accepts: groups of four
    # alphabet characters, the last one ending with no, one or two padding characters
    n = len(data)
    if n % 4 != 0:
        return False
    if n == 0:
        return True
    for i in range(n - 2):
        if not _digit(data[i]):
            return False
    if _digit(data[n - 2]):
        return _digit(data[n - 1]) or data[n - 1] == 61
    return data[n - 2] == 61 and data[n - 1] == 61


def _source(s) -> bytes:
    # the argument of a decoder as bytes (b64decode_internal()'s checks, with their messages)
    if isinstance(s, str):
        if not s.isascii():
            raise ValueError("string argument should contain only ASCII characters")
        return s.encode("ascii")
    if isinstance(s, bytes):
        return s
    raise TypeError("argument should be a bytes-like object or ASCII string")


def _decode(src: bytes, urlsafe: bool) -> bytes:
    if len(src) == 0:
        return b""
    if urlsafe:
        src = src.translate(_FROM_URLSAFE)
    # characters at the end that are neither of the alphabet nor padding are dropped first
    n = len(src)
    while n > 0 and not (_digit(src[n - 1]) or src[n - 1] == 61):
        n -= 1
    src = src[:n]
    if _wellformed(src):
        return binascii.a2b_base64(src)
    # b64decode_handle_invalid_input(): keep the alphabet's characters, and count the padding
    # characters that follow the last of them
    kept: list[int] = []
    pad = 0
    for c in src:
        if _digit(c):
            kept.append(c)
            pad = 0
        elif c == 61:
            pad += 1
    quad = len(kept) % 4
    if quad != 0 and quad + pad < 4:
        raise ValueError("Incorrect padding")
    if quad == 1:
        # one character and three padding characters: the C module's decoder rejects them, and
        # its last error is this one
        raise RuntimeError("base64_decode failed")
    return binascii.a2b_base64(bytes(kept) + b"=" * ((4 - quad) % 4))


def b64encode(s: bytes) -> bytes:
    """Encode bytes object using Base64."""
    if not isinstance(s, bytes):
        raise TypeError("base64() expects a bytes object")
    return binascii.b2a_base64(s, newline=False)


def b64decode(s) -> bytes:
    """Decode a Base64 encoded bytes object or ASCII string."""
    return _decode(_source(s), False)


def urlsafe_b64encode(s: bytes) -> bytes:
    """Encode bytes object using URL and file system safe Base64 alphabet."""
    if not isinstance(s, bytes):
        raise TypeError("base64() expects a bytes object")
    return binascii.b2a_base64(s, newline=False).translate(_TO_URLSAFE)


def urlsafe_b64decode(s) -> bytes:
    """Decode bytes or ASCII string using URL and file system safe Base64 alphabet."""
    return _decode(_source(s), True)
