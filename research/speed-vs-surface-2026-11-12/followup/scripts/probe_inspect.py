"""Probe only: inspect.cleandoc, to see what follows `import inspect`.

Adapted (annotations only) from CPython 3.13.16 Lib/inspect.py, Python Software Foundation
License Version 2; see tests/upstream/CPYTHON-LICENSE.txt on main.
"""


def cleandoc(doc: str) -> str:
    try:
        lines = doc.expandtabs().split('\n')
    except UnicodeError:
        return ""
    else:
        margin = 100000000
        for line in lines[1:]:
            content = len(line.lstrip())
            if content:
                indent = len(line) - content
                margin = min(margin, indent)
        if lines:
            lines[0] = lines[0].lstrip()
        if margin < 100000000:
            for i in range(1, len(lines)):
                lines[i] = lines[i][margin:]
        while lines and not lines[-1]:
            lines.pop()
        while lines and not lines[0]:
            lines.pop(0)
        return '\n'.join(lines)
