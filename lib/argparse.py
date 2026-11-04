"""Parse command lines for the static ArgumentParser schemas checked by the compiler."""

import sys
from typing import Callable
from _argparse_help import ArgSpec, action_name, format_help, format_usage, format_version


# Generated annotations keep these builtin types even when the client binds their names.
_Text = str
_Flag = bool


class Namespace:
    """Base of the record type the compiler creates for each parser."""

    def __eq__(self, other) -> bool:
        if not isinstance(other, Namespace):
            return False
        if self is other:
            return True
        # The compiler specializes a loop over field names. Each comparison
        # retains its own field types, including the caller's promoting ints.
        for name in vars(self):
            if not hasattr(other, name):
                return False
            if getattr(self, name) != getattr(other, name, None):
                return False
        for name in vars(other):
            if not hasattr(self, name):
                return False
        return True

    def __repr__(self) -> str:
        return 'Namespace()'


def ArgumentParser(*, _static_argparse_schema_required):
    # The loader replaces checked constructors with _Parser. An escaped
    # factory has no way to supply the required schema.
    raise NotImplementedError("ArgumentParser needs a static argparse schema")


class _Result:
    def __init__(self, size: int):
        self.values: list[list[str]] = []
        self.seen: list[bool] = []
        self.extras: list[str] = []
        for _ in range(size):
            empty: list[str] = []
            self.values.append(empty)
            self.seen.append(False)


def _decimal_digits(text: str) -> bool:
    if text.isascii():
        return text.isdecimal()
    # Native int accepts a single Unicode decimal digit, including scripts
    # outside the ASCII range supported by native str.isdecimal().
    for char in text:
        try:
            int(char)
        except ValueError:
            return False
    return True


def _negative_number(word: str) -> bool:
    # argparse accepts negative decimal integers and decimals with a
    # fractional part as values wherever an option could occur.
    if not word.startswith('-'):
        return False
    if word.endswith('\n'):
        word = word[:-1]  # The anchored decimal pattern also matches before a final newline.
    whole, dot, fraction = word[1:].partition('.')
    if dot:
        return (not whole or _decimal_digits(whole)) and _decimal_digits(fraction)
    return _decimal_digits(whole)


def _checked_integer(raw: str) -> str:
    return str(int(raw))


class _Parser:
    def __init__(self, prog: str | None = None, description: str | None = None,
                 add_help: bool = True, allow_abbrev: bool = True,
                 _int_text: Callable[[str], str] = _checked_integer):
        self.prog: str = sys.argv[0].rsplit('/', 1)[-1] if prog is None else prog
        self.description: str = '' if description is None else description
        self.add_help = add_help
        self.allow_abbrev = allow_abbrev
        self._int_text: Callable[[str], str] = _int_text
        self.specs: list[ArgSpec] = []
        self.options: dict[str, int] = {}
        self.positionals: list[int] = []
        if add_help:
            self.options['-h'] = -1
            self.options['--help'] = -1

    def _add(self, names: list[str], dest: str, action: str, converter: str,
             nargs: str, required: bool, choices: list[str], help_text: str, metavar: str, version: str):
        index = len(self.specs)
        options: list[str] = []
        if names and names[0].startswith('-'):
            options = names
            for name in names:
                self.options[name] = index
        else:
            self.positionals.append(index)
        self.specs.append(ArgSpec(options, dest, action, converter, nargs, required,
                                  choices, help_text, metavar, version))

    def format_usage(self) -> str:
        return format_usage(self.prog, self.add_help, self.specs)

    def format_help(self) -> str:
        return format_help(self.prog, self.description, self.add_help, self.specs)

    def print_usage(self) -> None:
        print(self.format_usage(), end='')

    def print_help(self) -> None:
        print(self.format_help(), end='')

    def exit(self, status: int = 0, message: str | None = None) -> None:
        if message is not None:
            print(message, end='', file=sys.stderr)
        sys.exit(status)

    def error(self, message: str) -> None:
        print(self.format_usage(), end='', file=sys.stderr)
        print(self.prog + ': error: ' + message, file=sys.stderr)
        sys.exit(2)

    def _check_values(self, spec: ArgSpec, raws: list[str]) -> None:
        # argparse converts every item for an action before checking its choices.
        converted: list[str] = []
        for raw in raws:
            value = raw
            try:
                if spec.converter == 'int':
                    value = self._int_text(raw)
                elif spec.converter == 'float':
                    value = str(float(raw))
            except ValueError:
                self.error('argument ' + action_name(spec) + ': invalid ' +
                           spec.converter + ' value: ' + repr(raw))
            if spec.choices:
                converted.append(value)
        for value in converted:
            matches = value in spec.choices
            if not matches and spec.converter == 'float':
                # Opposite signed zeros compare equal despite their spellings.
                matches = any([float(value) == float(choice) for choice in spec.choices])
            if not matches:
                display = [repr(item) for item in spec.choices]
                self.error('argument ' + action_name(spec) + ': invalid choice: ' +
                           repr(value) + ' (choose from ' + ', '.join(display) + ')')

    def _looks_like_option(self, word: str) -> bool:
        if len(word) < 2 or not word.startswith('-') or _negative_number(word):
            return False
        if ' ' not in word:
            return True
        # A space in an unknown name makes it positional; a space in an
        # attached value (including an abbreviated option's value) does not.
        if not word.startswith('--'):
            return word[:2] in self.options
        prefix = word.partition('=')[0]
        for name in self.options:
            if name == prefix or (self.allow_abbrev and name.startswith(prefix)):
                return True
        return False

    def _option(self, argv: list[str], start: int, separator: int, result: _Result) -> int:
        word = argv[start]
        option, eq, attached = word.partition('=')
        if option not in self.options:
            if word.startswith('--') and self.allow_abbrev:
                matches = [key for key in self.options if key.startswith(option)]
                if len(matches) > 1:
                    self.error('ambiguous option: ' + word + ' could match ' + ', '.join(matches))
                if not matches:
                    result.extras.append(word)
                    return start + 1
                option = matches[0]
            elif word[:2] in self.options:
                option = word[:2]
                attached = word[2:]
                eq = ''
            else:
                result.extras.append(word)
                return start + 1

        # A single dash may introduce a cluster of flags and an option value.
        flags: list[int] = []
        stop = start + 1
        while True:
            index = self.options[option]
            is_flag = index < 0 or self.specs[index].action != 'store'
            if not is_flag:
                if not eq and not attached:
                    if stop >= separator or self._looks_like_option(argv[stop]):
                        self.error('argument ' + action_name(self.specs[index]) +
                                   ': expected one argument')
                    attached = argv[stop]
                    stop += 1
                break
            if not eq and not attached:
                flags.append(index)
                break
            if len(option) != 2 or eq or attached.startswith('-'):
                label = '-h/--help' if index < 0 else action_name(self.specs[index])
                self.error('argument ' + label + ': ignored explicit argument ' + repr(attached))
            flags.append(index)
            option = '-' + attached[0]
            if option not in self.options:
                result.extras.append('-' + attached)
                break
            attached = attached[1:]
            if attached.startswith('='):
                eq = '='
                attached = attached[1:]

        for flag in flags:
            if flag == -1:
                self.print_help()
                sys.exit(0)
            if self.specs[flag].action == 'version':
                print(format_version(self.specs[flag].version, self.prog), end='')
                sys.exit(0)
            result.seen[flag] = True
        if not is_flag:
            result.values[index] = [attached]
            self._check_values(self.specs[index], result.values[index])
            result.seen[index] = True
        return stop

    def _positionals(self, argv: list[str], start: int, stop: int, separator: int,
                     position: int, result: _Result) -> int:
        # Consume the longest prefix of positional declarations that fits
        # before the next option. Reserve one value for each required field,
        # then let earlier optional fields take spare values from the left.
        remaining = stop - start
        if start <= separator < stop:
            remaining -= 1
        required = 0
        end = position
        while end < len(self.positionals):
            spec = self.specs[self.positionals[end]]
            if spec.required:
                if required == remaining:
                    break
                required += 1
            end += 1
        cursor = start
        while position < end:
            if cursor == stop and stop < len(argv):
                break
            index = self.positionals[position]
            arg = self.specs[index]
            if arg.required:
                required -= 1
            count = remaining - required
            if arg.nargs != '*' and arg.nargs != '+':
                count = min(count, 1)
            if cursor == separator and cursor < stop:
                cursor += 1
            for _ in range(count):
                raw = argv[cursor]
                result.values[index].append(raw)
                cursor += 1
                if cursor == separator and cursor < stop:
                    cursor += 1
            self._check_values(arg, result.values[index])
            result.seen[index] = count != 0 or arg.nargs == '*'
            remaining -= count
            position += 1
        result.extras.extend(argv[cursor:stop])
        return position

    def _parse(self, args: list[str] | None, known: bool) -> _Result:
        argv = sys.argv[1:] if args is None else args
        result = _Result(len(self.specs))
        separator = len(argv)
        for i in range(len(argv)):
            if argv[i] == '--':
                separator = i
                break
        start = 0
        position = 0
        while start < len(argv):
            if start < separator and self._looks_like_option(argv[start]):
                start = self._option(argv, start, separator, result)
            else:
                stop = start
                while stop < separator and not self._looks_like_option(argv[stop]):
                    stop += 1
                if stop >= separator:
                    stop = len(argv)
                position = self._positionals(argv, start, stop, separator, position, result)
                start = stop
        missing: list[str] = []
        for i in range(len(self.specs)):
            if self.specs[i].required and not result.seen[i]:
                missing.append(action_name(self.specs[i]))
        if missing:
            self.error('the following arguments are required: ' + ', '.join(missing))
        if not known and result.extras:
            self.error('unrecognized arguments: ' + ' '.join(result.extras))
        return result
