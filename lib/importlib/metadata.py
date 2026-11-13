"""The metadata of installed distribution packages."""
# Pystachy's subset implementation of CPython 3.13.16's Lib/importlib/metadata/__init__.py
# (lib/compatibility.md#importlibmetadata): version(), metadata(), requires(), distribution()
# and distributions() of the *.dist-info and *.egg-info directories on the module path, with
# CPython's name normalization, search order and messages. CPython searches sys.path as the
# program runs; Pystachy resolves imports while it compiles a program, so the directories
# searched are those in which the compiler looks for the program's modules (the compiler's
# primitive __pys_module_path(): the main program's directory, PYSTACHY_PATH, lib/), read as
# the program runs. A metadata file is parsed as CPython's email parser reads one
# (Lib/email/feedparser.py and the compat32 policy of Lib/email/_policybase.py), and held as
# _adapters.py's Message holds it; none of email, textwrap or re is imported for it.
import os

__all__ = [
    'Distribution',
    'PackageMetadata',
    'PackageNotFoundError',
    'PathDistribution',
    'distribution',
    'distributions',
    'metadata',
    'requires',
    'version',
]


class PackageNotFoundError(ModuleNotFoundError):
    """The package was not found."""

    # Pystachy port: the name is a field (CPython's property name unpacks self.args, which a
    # compiled exception does not have)
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name: str = name

    def __str__(self) -> str:
        return f"No package metadata was found for {self.name}"


def _lines(text: str) -> list[str]:
    # the lines of a text with their endings, as the feed parser's io.StringIO(newline='')
    # reads them: a line ends at "\n", "\r" or "\r\n", and at no other character
    lines: list[str] = []
    parts = text.split('\n')
    for number in range(len(parts)):
        ending = '\n' if number < len(parts) - 1 else ''
        pieces = parts[number].split('\r')
        for index in range(len(pieces) - 1):
            if index == len(pieces) - 2 and pieces[-1] == '' and ending:
                lines.append(pieces[index] + '\r\n')
            else:
                lines.append(pieces[index] + '\r')
        if pieces[-1] == '' and len(pieces) > 1:
            continue  # (the part ended with "\r": its last line is complete)
        if pieces[-1] + ending:
            lines.append(pieces[-1] + ending)
    return lines


def _is_newline(line: str) -> bool:
    # (feedparser.py's NLCRE.match(line))
    return line.startswith('\n') or line.startswith('\r')


def _is_header(line: str) -> bool:
    # feedparser.py's headerRE: a continuation line, a "From " line, or printable ASCII
    # characters other than a colon and then a colon
    if line.startswith(' ') or line.startswith('\t') or line.startswith('From '):
        return True
    for char in line:
        if char == ':':
            return True
        if not '!' <= char <= '~':
            return False
    return False


def _header(lines: list[str]) -> tuple[str, str]:
    # the compat32 policy's header_source_parse(): a header's name and its value, the folded
    # lines kept as they are
    cut = lines[0].find(':')
    value = (lines[0][cut + 1:] + ''.join(lines[1:])).lstrip(' \t\r\n')
    return (lines[0][:cut], value.rstrip('\r\n'))


def _dedent(text: str) -> str:
    # textwrap.dedent() (CPython 3.13.16's Lib/textwrap.py) without its regular expressions,
    # which would bring the regular expression engine into every program that reads a version:
    # the longest leading string of spaces and tabs common to all lines is removed, and lines
    # of spaces and tabs alone become empty
    lines = text.split('\n')
    margin = ''
    found = False
    for number in range(len(lines)):
        line = lines[number]
        rest = line.lstrip(' \t')
        if rest == '':
            lines[number] = ''
            continue
        indent = line[:len(line) - len(rest)]
        if not found:
            margin = indent
            found = True
        # Current line more deeply indented than previous winner:
        # no change (previous winner is still on top).
        elif indent.startswith(margin):
            pass
        # Current line consistent with and no deeper than previous winner:
        # it's the new winner.
        elif margin.startswith(indent):
            margin = indent
        # Find the largest common whitespace between current line and previous
        # winner.
        else:
            for i in range(min(len(margin), len(indent))):
                if margin[i] != indent[i]:
                    margin = margin[:i]
                    break
    if margin:
        for number in range(len(lines)):
            if lines[number].startswith(margin):
                lines[number] = lines[number][len(margin):]
    return '\n'.join(lines)


def _redent(value: str) -> str:
    "Correct for RFC822 indentation"
    if value == '' or '\n' not in value:
        return value
    return _dedent(' ' * 8 + value)


def _parse(text: str) -> list[tuple[str, str]]:
    # the headers of a message, as email.message_from_string() parses one that is not
    # multipart (feedparser.py's _parsegen and _parse_headers) and _adapters.Message repairs
    # them: the body is the header Description
    lines = _lines(text)
    count = 0
    while count < len(lines) and _is_header(lines[count]):
        count += 1
    rest = count
    if rest < len(lines) and _is_newline(lines[rest]):
        rest += 1  # (the separator; any other line begins the body)
    pushed = ''
    headers: list[tuple[str, str]] = []
    last: list[str] = []
    for number in range(count):
        line = lines[number]
        if line[0] in ' \t':
            if last:
                last.append(line)
            continue
        if last:
            headers.append(_header(last))
            last = []
        if line.startswith('From '):
            if number != 0 and number == count - 1:
                pushed = line  # (probably the first line of the body)
            continue
        if line.find(':') == 0:
            continue  # (no header name)
        last = [line]
    if last:
        headers.append(_header(last))
    result = [(key, _redent(value)) for key, value in headers]
    payload = pushed + ''.join(lines[rest:])
    if payload:
        result.append(('Description', payload))
    return result


class Message:
    """
    The metadata of a distribution package: the headers of its METADATA or PKG-INFO file, by
    name without regard to case, and its body as the header Description.
    """

    def __init__(self, text: str) -> None:
        self._headers = _parse(text)

    def __len__(self) -> int:
        """Return the total number of headers, including duplicates."""
        return len(self._headers)

    def __contains__(self, name: str) -> bool:
        name_lower = name.lower()
        for key, value in self._headers:
            if name_lower == key.lower():
                return True
        return False

    def __iter__(self):
        for field, value in self._headers:
            yield field

    def __getitem__(self, name: str) -> str:
        """Get a header value.

        Note that if the header appeared multiple times, exactly which
        occurrence gets returned is undefined.  Use get_all() to get all
        the values matching a header field name.
        """
        name_lower = name.lower()
        for key, value in self._headers:
            if key.lower() == name_lower:
                return value
        # (CPython 3.13 warns that this "will raise KeyErrors", and returns None)
        raise KeyError(name)

    def keys(self) -> list[str]:
        """Return a list of all the message's header field names.

        These will be sorted in the order they appeared in the original
        message, or were added to the message, and may contain duplicates.
        """
        return [key for key, value in self._headers]

    def values(self) -> list[str]:
        """Return a list of all the message's header values.

        These will be sorted in the order they appeared in the original
        message, or were added to the message, and may contain duplicates.
        """
        return [value for key, value in self._headers]

    def items(self) -> list[tuple[str, str]]:
        """Get all the message's header fields and values.

        These will be sorted in the order they appeared in the original
        message, or were added to the message, and may contain duplicates.
        """
        return list(self._headers)

    def get(self, name: str, failobj: str | None = None) -> str | None:
        """Get a header value.

        Like __getitem__() but return failobj instead of None when the field
        is missing.
        """
        name_lower = name.lower()
        for key, value in self._headers:
            if key.lower() == name_lower:
                return value
        return failobj

    def get_all(self, name: str, failobj: list[str] | None = None) -> list[str] | None:
        """Return a list of all the values for the named field.

        These will be sorted in the order they appeared in the original
        message, and may contain duplicates.  Any fields deleted and
        re-inserted are always appended to the header list.

        If no such fields exist, failobj is returned (defaults to None).
        """
        values: list[str] = []
        name_lower = name.lower()
        for key, value in self._headers:
            if key.lower() == name_lower:
                values.append(value)
        if not values:
            return failobj
        return values


PackageMetadata = Message


def _normalize(name: str) -> str:
    """
    PEP 503 normalization plus dashes as underscores.
    """
    # (Prepared.normalize: re.sub(r"[-_.]+", "-", name).lower().replace('-', '_'))
    parts: list[str] = []
    run = False
    for char in name:
        if char in '-_.':
            if not run:
                parts.append('_')
            run = True
        else:
            parts.append(char)
            run = False
    return ''.join(parts).lower()


def _requirements(source: str) -> list[str]:
    # Distribution._deps_from_requires_text(): the lines of an egg-info requires.txt, each with
    # its section's extra and markers (Sectioned.read and
    # _convert_egg_info_reqs_to_simple_reqs)
    result: list[str] = []
    section = ''
    for line in source.splitlines():
        value = line.strip()
        if value == '':
            continue
        if value.startswith('[') and value.endswith(']'):
            section = value.strip('[]')
            continue
        extra, sep, markers = section.partition(':')
        if extra and markers:
            markers = f'({markers})'
        conditions: list[str] = []
        if markers:
            conditions.append(markers)
        if extra:
            conditions.append(f'extra == "{extra}"')
        marker = '; ' + ' and '.join(conditions) if conditions else ''
        # PEP 508 requires a space between the url_spec and the quoted_marker.
        # '@' is uniquely indicative of a url_req.
        result.append(value + (' ' if '@' in value else '') + marker)
    return result


class Distribution:
    """
    An abstract Python distribution package.

    Custom providers may derive from this class and define
    the abstract methods to provide a concrete implementation
    for their environment. Some providers may opt to override
    the default implementation of some properties to bypass
    the file-reading mechanism.
    """

    def read_text(self, filename: str) -> str | None:
        """Attempt to load metadata file given by the name.

        Python distribution metadata is organized by blobs of text
        typically represented as "files" in the metadata directory
        (e.g. package-1.0.dist-info). These files include things
        like:

        - METADATA: The distribution metadata including fields
          like Name and Version and Description.
        - entry_points.txt: A series of entry points as defined in
          `the entry points spec <https://packaging.python.org/en/latest/specifications/entry-points/#file-format>`_.
        - RECORD: A record of files according to
          `this recording spec <https://packaging.python.org/en/latest/specifications/recording-installed-packages/#the-record-file>`_.

        A package may provide any set of files, including those
        not listed here or none at all.

        :param filename: The name of the file in the distribution info.
        :return: The text if found, otherwise None.
        """
        raise NotImplementedError

    @staticmethod
    def from_name(name: str) -> 'Distribution':
        """Return the Distribution for the given package name.

        :param name: The name of the distribution package to search for.
        :return: The Distribution instance (or subclass thereof) for the named
            package, if found.
        :raises PackageNotFoundError: When the named package's distribution
            metadata cannot be found.
        :raises ValueError: When an invalid value is supplied for name.
        """
        if not name:
            raise ValueError("A distribution name is required.")
        found = _search(name, True)
        if not found:
            raise PackageNotFoundError(name)
        return PathDistribution(found[0])

    @property
    def metadata(self) -> Message:
        """Return the parsed metadata for this Distribution.

        The returned object will have keys that name the various bits of
        metadata per the
        `Core metadata specifications <https://packaging.python.org/en/latest/specifications/core-metadata/#core-metadata>`_.

        Custom providers may provide the METADATA file or override this
        property.
        """
        text = self.read_text('METADATA')
        if not text:
            text = self.read_text('PKG-INFO')
        if not text:
            # This last clause is here to support old egg-info files.  Its
            # effect is to just end up using the PathDistribution's self._path
            # (which points to the egg-info file) attribute unchanged.
            text = self.read_text('')
        return Message(text if text is not None else '')

    @property
    def name(self) -> str:
        """Return the 'Name' metadata for the distribution package."""
        return self.metadata['Name']

    @property
    def version(self) -> str:
        """Return the 'Version' metadata for the distribution package."""
        return self.metadata['Version']

    @property
    def requires(self) -> list[str] | None:
        """Generated requirements specified for this Distribution"""
        reqs = self.metadata.get_all('Requires-Dist')
        if reqs:
            return reqs
        source = self.read_text('requires.txt')
        if source is None:
            return reqs
        return _requirements(source)


class PathDistribution(Distribution):
    def __init__(self, path: str) -> None:
        """Construct a distribution.

        :param path: SimplePath indicating the metadata directory.
        """
        self._path = path

    def read_text(self, filename: str) -> str | None:
        # (pathlib's joinpath('') is the path itself: an egg-info file)
        path = os.path.join(self._path, filename) if filename else self._path
        try:
            with open(path, encoding='utf-8') as file:
                return file.read()
        except (FileNotFoundError, IsADirectoryError, NotADirectoryError, PermissionError):
            return None


def _search(name: str, named: bool) -> list[str]:
    # the metadata directories of the module path's directories, in their order: those of the
    # distribution name, or of every distribution (FastPath, Lookup and Lookup.search)
    normalized = _normalize(name)
    result: list[str] = []
    for root in __pys_module_path():
        try:
            children = os.listdir(root)
        except OSError:
            continue  # (CPython then reads a zip file: none is read here)
        infos: dict[str, list[str]] = {}
        for child in children:
            low = child.lower()
            if low.endswith('.dist-info') or low.endswith('.egg-info'):
                # rpartition is faster than splitext and suitable for this purpose.
                key = _normalize(low.rpartition('.')[0].partition('-')[0])
                if not named or key == normalized:
                    if key not in infos:
                        infos[key] = []
                    infos[key].append(os.path.join(root, child))
        for key in infos:
            result.extend(infos[key])
    return result


def distribution(distribution_name: str) -> Distribution:
    """Get the ``Distribution`` instance for the named package.

    :param distribution_name: The name of the distribution package as a string.
    :return: A ``Distribution`` instance (or subclass thereof).
    """
    return Distribution.from_name(distribution_name)


def distributions() -> list[Distribution]:
    """Get all ``Distribution`` instances in the current environment.

    :return: An iterable of ``Distribution`` instances.
    """
    result: list[Distribution] = []
    for path in _search('', False):
        result.append(PathDistribution(path))
    return result


def metadata(distribution_name: str) -> Message:
    """Get the metadata for the named package.

    :param distribution_name: The name of the distribution package to query.
    :return: A PackageMetadata containing the parsed metadata.
    """
    return Distribution.from_name(distribution_name).metadata


def version(distribution_name: str) -> str:
    """Get the version string for the named package.

    :param distribution_name: The name of the distribution package to query.
    :return: The version string for the package as defined in the package's
        "Version" metadata key.
    """
    return distribution(distribution_name).version


def requires(distribution_name: str) -> list[str] | None:
    """
    Return a list of requirements for the named package.

    :return: An iterable of requirements, suitable for
        packaging.requirement.Requirement.
    """
    return distribution(distribution_name).requires
