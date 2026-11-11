"""Probe stand-in for librt.base64; bodies raise."""


def b64encode(s: bytes) -> bytes:
    raise NotImplementedError("librt.base64.b64encode")


def b64decode(s: bytes | str) -> bytes:
    raise NotImplementedError("librt.base64.b64decode")


def urlsafe_b64encode(s: bytes) -> bytes:
    raise NotImplementedError("librt.base64.urlsafe_b64encode")


def urlsafe_b64decode(s: bytes | str) -> bytes:
    raise NotImplementedError("librt.base64.urlsafe_b64decode")
