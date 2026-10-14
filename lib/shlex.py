"""A lexical analyzer class for simple shell-like syntaxes."""

# Module and documentation by Eric S. Raymond, 21 Dec 1998
# Input stacking and error message cleanup added by ESR, March 2000
# push_source() and pop_source() made explicit by ESR, January 2001.
# Posix compliance, split(), string arguments, and
# iterator interface by Gustavo Niemeyer, April 2003.
# changes to tokenize more like Posix shells by Vinay Sajip, July 2016.

import os
import posixpath  # Pystachy port: (see sourcehook())
import re
import sys
from typing import Iterator  # Pystachy port: (see __iter__())
from collections import deque

from io import StringIO

__all__ = ["shlex", "split", "quote", "join"]

# Pystachy port: typed empty lists let the existing constructor infer deque item types.
def _empty_tokens() -> list[str]:
    return []


def _empty_sources() -> list[tuple[str | None, StringIO, int]]:
    return []


class shlex:
    "A lexical analyzer class for simple shell-like syntaxes."
    def __init__(self, instream=None, infile=None, posix=False,
                 punctuation_chars=False):
        # Pystachy port: the lexer reads a StringIO, also of the text of a file, which it reads
        # whole here (CPython's reads the file as it asks for characters): a field has one type,
        # and the streams of a str and of the sources it pushes are StringIOs
        if isinstance(instream, str):
            self.instream = StringIO(instream)
        elif isinstance(instream, StringIO):
            self.instream = instream
        elif instream is not None:
            self.instream = StringIO(instream.read())
        else:
            self.instream = StringIO(sys.stdin.read())
        self.infile: str | None = infile if instream is not None else None  # Pystachy port: (above)
        self.posix = posix
        self.eof: str | None = None if posix else ''  # Pystachy port: annotated, None or ''
        self.commenters = '#'
        self.wordchars = ('abcdfeghijklmnopqrstuvwxyz'
                          'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_')
        if self.posix:
            self.wordchars += ('ßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ'
                               'ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞ')
        self.whitespace = ' \t\r\n'
        self.whitespace_split = False
        self.quotes = '\'"'
        self.escape = '\\'
        self.escapedquotes = '"'
        self.state: str | None = ' '  # Pystachy port: annotated (None past the end of the input)
        self.pushback = deque(_empty_tokens())  # Pystachy port: typed empty list argument
        self.lineno = 1
        self.debug = 0
        self.token = ''
        self.filestack = deque(_empty_sources())  # Pystachy port: (above)
        self.source: str | None = None  # Pystachy port: annotated (a str where sources are read)
        # Pystachy port: chars, for punctuation_chars, a bool or a str (a variable has one type)
        if isinstance(punctuation_chars, bool):
            chars = '();<>|&' if punctuation_chars else ''
        else:
            chars = punctuation_chars
        # Pystachy port: punctuation_chars is a field (a class template's method has no
        # decorator), and _pushback_chars is made also without punctuation_chars, typed
        self.punctuation_chars: str = chars
        # _pushback_chars is a push back queue used by lookahead logic
        self._pushback_chars = deque(_empty_tokens())  # Pystachy port: (above)
        if chars:
            # these chars added because allowed in file names, args, wildcards
            self.wordchars += '~-./*?='
            #remove any punctuation chars from wordchars
            # Pystachy port: no str.translate(); wordchars contains only ASCII/Latin-1.
            # Code points preserve UTF-8 characters instead of removing shared prefix bytes.
            for cp in range(256):
                char = '%c' % cp
                if char in chars:
                    self.wordchars = self.wordchars.replace(char, '')

    # Pystachy port: punctuation_chars is a field, set by __init__ (above)

    def push_token(self, tok):
        "Push a token onto the stack popped by the get_token method"
        if self.debug >= 1:
            print("shlex: pushing token " + repr(tok))
        self.pushback.appendleft(tok)

    def push_source(self, newstream, newfile=None):
        "Push an input source onto the lexer's input source stack."
        # Pystachy port: a StringIO, as in __init__; a file is read whole and closed here, where
        # CPython's pop_source() closes it
        if isinstance(newstream, str):
            stream = StringIO(newstream)
        elif isinstance(newstream, StringIO):
            stream = newstream
        else:
            stream = StringIO(newstream.read())
            newstream.close()
        self.filestack.appendleft((self.infile, self.instream, self.lineno))
        self.infile = newfile
        self.instream = stream
        self.lineno = 1
        if self.debug:
            if newfile is not None:
                print('shlex: pushing to file %s' % (self.infile,))
            else:
                print('shlex: pushing to stream %s' % (self.instream,))

    def pop_source(self):
        "Pop the input source stack."
        self.instream.close()
        (self.infile, self.instream, self.lineno) = self.filestack.popleft()
        if self.debug:
            print('shlex: popping to %s, line %d' \
                  % (self.instream, self.lineno))
        self.state = ' '

    def get_token(self) -> str | None:  # Pystachy port: annotated (it calls itself)
        "Get a token from the input stream (or from stack if it's nonempty)"
        if self.pushback:
            tok = self.pushback.popleft()
            if self.debug >= 1:
                print("shlex: popping token " + repr(tok))
            return tok
        # No pushback.  Get a token.
        raw = self.read_token()
        # Handle inclusions
        if self.source is not None:
            while raw == self.source:
                spec = self.sourcehook(self.read_token())
                if spec:
                    (newfile, newstream) = spec
                    self.push_source(newstream, newfile)
                raw = self.get_token()
        # Maybe we got EOF instead?
        while raw == self.eof:
            if not self.filestack:
                return self.eof
            else:
                self.pop_source()
                raw = self.get_token()
        # Neither inclusion nor EOF
        if self.debug >= 1:
            if raw != self.eof:
                print("shlex: token=" + repr(raw))
            else:
                print("shlex: token=EOF")
        return raw

    def read_token(self):
        quoted = False
        escapedstate = ' '
        while True:
            if self.punctuation_chars and self._pushback_chars:
                nextchar = self._pushback_chars.pop()
            else:
                nextchar = self.instream.read(1)
                # Pystachy port: a character past ASCII is read whole, where read(1) reads a byte
                # of its UTF-8 (a str holds UTF-8 in Pystachy, whose len("\xe9") is 2): the
                # bytes that the first one says follow it
                if len("\xe9") == 2 and nextchar and ord(nextchar) >= 0xC2:
                    b = ord(nextchar)
                    nextchar += self.instream.read(3 if b >= 0xF0 else 2 if b >= 0xE0 else 1)
            if nextchar == '\n':
                self.lineno += 1
            if self.debug >= 3:
                print("shlex: in state %r I see character: %r" % (self.state,
                                                                  nextchar))
            state = self.state  # Pystachy port: a local, which the tests narrow (a field is not)
            if state is None:  # Pystachy port: (state)
                self.token = ''        # past end of file
                break
            elif state == ' ':  # Pystachy port: (state)
                if not nextchar:
                    self.state = None  # end of file
                    break
                elif nextchar in self.whitespace:
                    if self.debug >= 2:
                        print("shlex: I see whitespace in whitespace state")
                    if self.token or (self.posix and quoted):
                        break   # emit current token
                    else:
                        continue
                elif nextchar in self.commenters:
                    self.instream.readline()
                    self.lineno += 1
                elif self.posix and nextchar in self.escape:
                    escapedstate = 'a'
                    self.state = nextchar
                elif nextchar in self.wordchars:
                    self.token = nextchar
                    self.state = 'a'
                elif nextchar in self.punctuation_chars:
                    self.token = nextchar
                    self.state = 'c'
                elif nextchar in self.quotes:
                    if not self.posix:
                        self.token = nextchar
                    self.state = nextchar
                elif self.whitespace_split:
                    self.token = nextchar
                    self.state = 'a'
                else:
                    self.token = nextchar
                    if self.token or (self.posix and quoted):
                        break   # emit current token
                    else:
                        continue
            elif state in self.quotes:  # Pystachy port: (state)
                quoted = True
                if not nextchar:      # end of file
                    if self.debug >= 2:
                        print("shlex: I see EOF in quotes state")
                    # XXX what error should be raised here?
                    raise ValueError("No closing quotation")
                if nextchar == state:  # Pystachy port: (state)
                    if not self.posix:
                        self.token += nextchar
                        self.state = ' '
                        break
                    else:
                        self.state = 'a'
                elif (self.posix and nextchar in self.escape and state  # Pystachy port: (state)
                      in self.escapedquotes):
                    escapedstate = state  # Pystachy port: (state)
                    self.state = nextchar
                else:
                    self.token += nextchar
            elif state in self.escape:  # Pystachy port: (state)
                if not nextchar:      # end of file
                    if self.debug >= 2:
                        print("shlex: I see EOF in escape state")
                    # XXX what error should be raised here?
                    raise ValueError("No escaped character")
                # In posix shells, only the quote itself or the escape
                # character may be escaped within quotes.
                if (escapedstate in self.quotes and
                        nextchar != state and nextchar != escapedstate):  # Pystachy port: (state)
                    self.token += state  # Pystachy port: (state)
                self.token += nextchar
                self.state = escapedstate
            elif state in ('a', 'c'):  # Pystachy port: (state)
                if not nextchar:
                    self.state = None   # end of file
                    break
                elif nextchar in self.whitespace:
                    if self.debug >= 2:
                        print("shlex: I see whitespace in word state")
                    self.state = ' '
                    if self.token or (self.posix and quoted):
                        break   # emit current token
                    else:
                        continue
                elif nextchar in self.commenters:
                    self.instream.readline()
                    self.lineno += 1
                    if self.posix:
                        self.state = ' '
                        if self.token or (self.posix and quoted):
                            break   # emit current token
                        else:
                            continue
                elif state == 'c':  # Pystachy port: (state)
                    if nextchar in self.punctuation_chars:
                        self.token += nextchar
                    else:
                        if nextchar not in self.whitespace:
                            self._pushback_chars.append(nextchar)
                        self.state = ' '
                        break
                elif self.posix and nextchar in self.quotes:
                    self.state = nextchar
                elif self.posix and nextchar in self.escape:
                    escapedstate = 'a'
                    self.state = nextchar
                elif (nextchar in self.wordchars or nextchar in self.quotes
                      or (self.whitespace_split and
                          nextchar not in self.punctuation_chars)):
                    self.token += nextchar
                else:
                    if self.punctuation_chars:
                        self._pushback_chars.append(nextchar)
                    else:
                        self.pushback.appendleft(nextchar)
                    if self.debug >= 2:
                        print("shlex: I see punctuation in word state")
                    self.state = ' '
                    if self.token or (self.posix and quoted):
                        break   # emit current token
                    else:
                        continue
        result: str | None = self.token  # Pystachy port: annotated (None at the end)
        self.token = ''
        if self.posix and not quoted and result == '':
            result = None
        if self.debug > 1:
            if result:
                print("shlex: raw token=" + repr(result))
            else:
                print("shlex: raw token=EOF")
        return result

    def sourcehook(self, newfile):
        "Hook called on a filename to be sourced."
        # Pystachy port: newfile, a token, is a str or None, as None[0] raises (narrowed here)
        if newfile is None:
            raise TypeError("'NoneType' object is not subscriptable")
        if newfile[0] == '"':
            newfile = newfile[1:-1]
        # This implements cpp-like semantics for relative-path inclusion.
        # Pystachy port: posixpath's isabs() and dirname(), as os.path is posixpath on POSIX and
        # Pystachy's os.path has neither, of infile, a local that isinstance() narrows
        infile = self.infile
        if isinstance(infile, str) and not posixpath.isabs(newfile):
            newfile = os.path.join(posixpath.dirname(infile), newfile)
        return (newfile, open(newfile, "r"))

    def error_leader(self, infile=None, lineno=None):
        "Emit a C-compiler-like, Emacs-friendly error-message leader."
        if infile is None:
            infile = self.infile
        if lineno is None:
            lineno = self.lineno
        return "\"%s\", line %d: " % (infile, lineno)

    def __iter__(self) -> Iterator[str]:
        # Pystachy port: annotated, and the tokens left, read when the loop starts (an iterator
        # class, which reads each token as the loop asks for it, is not supported)
        tokens = []
        while True:
            token = self.get_token()
            if token is None or token == self.eof:
                break
            tokens.append(token)
        return iter(tokens)

    def __next__(self) -> str | None:  # Pystachy port: annotated (a special method of a class template)
        token = self.get_token()
        if token == self.eof:
            raise StopIteration
        return token

def split(s, comments=False, posix=True):
    """Split the string *s* using shell-like syntax."""
    if s is None:
        raise ValueError("s argument must not be None")
    lex = shlex(s, posix=posix)
    lex.whitespace_split = True
    if not comments:
        lex.commenters = ''
    return list(lex)


def join(split_command):
    """Return a shell-escaped string from *split_command*."""
    return ' '.join(quote(arg) for arg in split_command)


_find_unsafe = re.compile(r'[^\w@%+=:,./-]', re.ASCII).search

def quote(s):
    """Return a shell-escaped version of the string *s*."""
    if not s:
        return "''"
    if _find_unsafe(s) is None:
        return s

    # use single quotes, and put single quotes into double quotes
    # the string $'b is then quoted as '$'"'"'b'
    return "'" + s.replace("'", "'\"'\"'") + "'"


def _print_tokens(lexer):
    while tt := lexer.get_token():
        print("Token: " + repr(tt))

if __name__ == '__main__':
    if len(sys.argv) == 1:
        _print_tokens(shlex())
    else:
        fn = sys.argv[1]
        with open(fn) as f:
            _print_tokens(shlex(f, fn))
