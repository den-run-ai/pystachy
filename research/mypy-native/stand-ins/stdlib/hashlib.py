# Probe stub: a throwing hashlib, only to see past mypy/util.py's import.
class _Hash:
    def digest(self) -> bytes:
        raise NotImplementedError("hashlib stub")

    def hexdigest(self) -> str:
        raise NotImplementedError("hashlib stub")


def sha1(data: bytes) -> _Hash:
    return _Hash()


def sha256(data: bytes) -> _Hash:
    return _Hash()
