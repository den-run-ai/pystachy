# pystachy: dynamic-any
"""Shared finally continuations preserve payloads and their independent identities."""
from typing import Any

events: list[str] = []


def literals(flag: bool) -> int:
    try:
        if flag:
            return 1
        return 2
    finally:
        try:
            events.append("outer")
        finally:
            events.append("inner")


def preserved(value: float, replacement: float) -> float:
    try:
        return value
    finally:
        try:
            value = replacement
        finally:
            events.append("preserved")


def overridden(flag: bool, replacement: float) -> float:
    try:
        return 1.5
    finally:
        try:
            if flag:
                return replacement
        finally:
            events.append("overridden")


def cancelled(flag: bool) -> int:
    for i in range(1):
        try:
            return 1
        finally:
            try:
                if flag:
                    break
            finally:
                events.append("cancelled")
    return 3


def failed() -> int:
    try:
        return 1
    finally:
        try:
            raise ValueError("cleanup")
        finally:
            events.append("failed")


print(literals(True), literals(False), events)
events.clear()
first: Any = float("nan")
second: Any = float("nan")
print(preserved(first, second) is first)
print(overridden(True, second) is second, overridden(False, second))
print(cancelled(True), cancelled(False))
try:
    failed()
except ValueError as error:
    print(str(error))
print(events)
