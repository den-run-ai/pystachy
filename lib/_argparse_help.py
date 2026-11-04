"""Help and usage for the checked argparse schema (CPython 3.13 conventions)."""

import os
from textwrap import wrap


class ArgSpec:
    def __init__(self, options: list[str], dest: str, action: str, converter: str,
                 nargs: str, required: bool, choices: list[str], help_text: str, metavar: str, version: str):
        self.options = options
        self.dest = dest
        self.action = action
        self.converter = converter
        self.nargs = nargs
        self.required = required
        self.choices = choices
        self.help_text = help_text
        self.metavar = metavar
        self.version = version


def action_name(spec: ArgSpec) -> str:
    if spec.options:
        return "/".join(spec.options)
    return spec.metavar or spec.dest


def metavar_for(spec: ArgSpec) -> str:
    if spec.metavar:
        return spec.metavar
    if spec.choices:
        return "{" + ",".join(spec.choices) + "}"
    if spec.options:
        return spec.dest.upper()
    return spec.dest


def _args(spec: ArgSpec) -> str:
    metavar = metavar_for(spec)
    if spec.nargs == "?":
        return "[" + metavar + "]"
    if spec.nargs == "*":
        return "[" + metavar + " ...]"
    if spec.nargs == "+":
        return metavar + " [" + metavar + " ...]"
    return metavar


def _invocation(spec: ArgSpec) -> str:
    if not spec.options:
        return metavar_for(spec)
    header = ", ".join(spec.options)
    if spec.action == "store":
        header += " " + _args(spec)
    return header


def _width() -> int:
    # Honor the shell override; redirected output and terminals without an
    # override use the standard 80-column fallback (no terminal ioctl).
    try:
        columns = int(os.getenv("COLUMNS", "80"))
    except ValueError:
        columns = 80
    return columns - 2 if columns > 0 else 78


def _usage_lines(parts: list[str], indent: int, width: int, first: str = "") -> list[str]:
    lines: list[str] = []
    pad = " " * indent
    line = first
    for part in parts:
        if line and len(line) + 1 + len(part) > width:
            lines.append(line)
            line = ""
        if line:
            line += " " + part
        else:
            line = pad + part
    if line:
        lines.append(line)
    return lines


def _usage(prog: str, add_help: bool, specs: list[ArgSpec], width: int) -> str:
    prefix = "usage: "
    start = prefix + prog
    options: list[str] = []
    positions: list[str] = []
    if add_help:
        options.append("[-h]")
    for spec in specs:
        if spec.options:
            part = spec.options[0]
            if spec.action == "store":
                part += " " + _args(spec)
            options.append(part if spec.required else "[" + part + "]")
        else:
            positions.append(_args(spec))
    parts = options + positions
    if not parts:
        return start + "\n"
    line = start + (" " if prog else "") + " ".join(parts)
    if len(line) <= width:
        return line + "\n"
    if len(start) * 4 <= 3 * width:
        indent = len(start) + 1
        if options:
            lines = _usage_lines(options, indent, width, start)
            lines.extend(_usage_lines(positions, indent, width))
        else:
            lines = _usage_lines(positions, indent, width, start)
    else:
        indent = len(prefix)
        lines = _usage_lines(parts, indent, width)
        if len(lines) > 1:
            lines = _usage_lines(options, indent, width)
            lines.extend(_usage_lines(positions, indent, width))
        lines.insert(0, start)
    return "\n".join(lines) + "\n"


def format_usage(prog: str, add_help: bool, specs: list[ArgSpec]) -> str:
    return _usage(prog, add_help, specs, _width())


def _expand(text: str, prog: str) -> str:
    # The schema accepts only the two escapes below. Splitting on %% first
    # keeps an escaped %(prog)s literal and leaves prog's own '%' untouched.
    return "%".join([part.replace("%(prog)s", prog) for part in text.split("%%")])


def _wrap(text: str, width: int) -> list[str]:
    # argparse collapses ASCII whitespace before handing lines to textwrap.
    for char in "\r\n\t\v\f":
        text = text.replace(char, " ")
    words = [word for word in text.split(" ") if word]
    return wrap(" ".join(words).strip(), width)


def _entry(label: str, help_text: str, column: int, width: int) -> str:
    header = "  " + label
    if not help_text:
        return header + "\n"
    if len(header) + 2 > column:
        if not help_text.strip():
            return header + "\n"
        header += "\n" + " " * column
    else:
        header += " " * (column - len(header))
    lines = _wrap(help_text, max(11, width - column))
    return header + ("\n" + " " * column).join(lines) + "\n"


def _format_text(text: str, prog: str, width: int) -> str:
    if "%(prog)" in text:
        text = _expand(text, prog)
    return "\n".join(_wrap(text, max(width, 11))) + "\n"


def format_version(text: str, prog: str) -> str:
    return _format_text(text, prog, _width())


def format_help(prog: str, description: str, add_help: bool, specs: list[ArgSpec]) -> str:
    width = _width()
    text = _usage(prog, add_help, specs, width)
    if description.strip():
        text += "\n" + _format_text(description, prog, width)
    longest = len("-h, --help") if add_help else 0
    for spec in specs:
        longest = max(longest, len(_invocation(spec)))
    column = min(longest + 4, min(24, max(width - 20, 4)))
    positional = ""
    optional = ""
    if add_help:
        optional += _entry("-h, --help", "show this help message and exit", column, width)
    for spec in specs:
        item = _entry(_invocation(spec), _expand(spec.help_text, prog), column, width)
        if spec.options:
            optional += item
        else:
            positional += item
    if positional:
        text += "\npositional arguments:\n" + positional
    if optional:
        text += "\noptions:\n" + optional
    return text.rstrip("\n") + "\n"
