# pystachy: python-int
"""Promote an overflowing JSON integer without promoting scanner indices."""


def _integer(token: str) -> int:
    return int(token)
