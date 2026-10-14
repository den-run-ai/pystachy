"""Reusable typed Python; the dependency is an ordinary installed source wheel."""
from roman import toRoman


def label(n: int) -> str:
    return "Chapter " + toRoman(n)
