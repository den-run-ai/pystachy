# subprocess - Subprocesses with accessible I/O streams
#
# For more information about this module, see PEP 324.
#
# Copyright (c) 2003-2005 by Peter Astrand <astrand@lysator.liu.se>
#
# Licensed to PSF under a Contributor Agreement.

r"""Subprocesses with accessible I/O streams

This module allows you to spawn processes, connect to their
input/output/error pipes, and obtain their return codes.

For a complete description of this module see the Python documentation.

Main API
========
run(...): Runs a command, waits for it to complete, then returns a
          CompletedProcess instance.
Popen(...): A class for flexibly executing a command in a new process

Constants
---------
DEVNULL: Special value that indicates that os.devnull should be used
PIPE:    Special value that indicates a pipe should be created
STDOUT:  Special value that indicates that stderr should go to stdout


Older API
=========
call(...): Runs a command, waits for it to complete, then returns
    the return code.
check_call(...): Same as call() but raises CalledProcessError()
    if return code is not 0
check_output(...): Same as check_call() but returns the contents of
    stdout instead of a return code
getoutput(...): Runs a command in the shell, waits for it to complete,
    then returns the output
getstatusoutput(...): Runs a command in the shell, waits for it to complete,
    then returns a (exitcode, output) tuple
"""

# Pystachy's subset implementation of CPython 3.13.16's Lib/subprocess.py, for POSIX
# (lib/compatibility.md#subprocess). CPython's module is written over os, select, io and
# _posixsubprocess.fork_exec(); this one is written over the private primitives that do their
# part of it (__pys_proc_*, runtime.c), with CPython's steps in CPython's order. What CPython
# decides from its arguments as it runs, the functions decide when the program is compiled,
# from the arguments' types. One is text mode: a call of run() or check_output() that passes
# text, universal_newlines, encoding or errors returns str, another bytes, as typeshed's
# overloads say. The other is what stdin, stdout and stderr are: None, an int (PIPE, STDOUT,
# DEVNULL or a file descriptor) or an open file. A Popen is of one type, so that an annotation
# names it and a field holds it: its pipes carry bytes, through communicate() (it has no
# stdin, stdout and stderr files), and its streams are None or ints.
import os
import sys
import time
from types import GenericAlias
from typing import Any, Generic, TypeVar

__all__ = ["Popen", "PIPE", "STDOUT", "call", "check_call", "getstatusoutput",
           "getoutput", "check_output", "run", "CalledProcessError", "DEVNULL",
           "SubprocessError", "TimeoutExpired", "CompletedProcess"]
           # NOTE: We intentionally exclude list2cmdline as it is
           # considered an internal implementation detail.  issue10838.


# Exception classes used by this module.
class SubprocessError(Exception): pass


class CalledProcessError(SubprocessError):
    """Raised when run() is called with check=True and the process
    returns a non-zero exit status.

    Attributes:
      cmd, returncode, stdout, stderr, output
    """
    # Pystachy port: output and stderr are bytes, also those of a call in text mode, which are
    # the bytes before they are decoded (CPython's are then the str): a field has one type, and
    # a union does not hold bytes
    def __init__(self, returncode: int, cmd: str | list[str], output: bytes | None = None,
                 stderr: bytes | None = None) -> None:
        self.returncode = returncode
        self.cmd = cmd
        self.output = output
        self.stderr = stderr

    def __str__(self) -> str:
        if self.returncode < 0:
            # Pystachy port: the signal's name of the runtime, as there is no signal module
            name = __pys_proc_signame(-self.returncode)
            if name != "":
                return f"Command '{self.cmd}' died with <Signals.{name}: {-self.returncode}>."
            return f"Command '{self.cmd}' died with unknown signal {-self.returncode}."
        else:
            return (f"Command '{self.cmd}' returned non-zero "
                    f"exit status {self.returncode}.")

    @property
    def stdout(self) -> bytes | None:
        """Alias for output attribute, to match stderr"""
        return self.output

    @stdout.setter
    def stdout(self, value: bytes | None) -> None:
        # There's no obvious reason to set this, but allow it anyway so
        # .stdout is a transparent alias for .output
        self.output = value


class TimeoutExpired(SubprocessError):
    """This exception is raised when the timeout expires while waiting for a
    child process.

    Attributes:
        cmd, output, stdout, stderr, timeout
    """
    def __init__(self, cmd: str | list[str], timeout: int | float | None, output: bytes | None = None,
                 stderr: bytes | None = None) -> None:
        self.cmd = cmd
        self.timeout = timeout
        self.output = output
        self.stderr = stderr

    def __str__(self) -> str:
        return f"Command '{self.cmd}' timed out after {self.timeout} seconds"

    @property
    def stdout(self) -> bytes | None:
        return self.output

    @stdout.setter
    def stdout(self, value: bytes | None) -> None:
        # There's no obvious reason to set this, but allow it anyway so
        # .stdout is a transparent alias for .output
        self.output = value


PIPE = -1
STDOUT = -2
DEVNULL = -3

# When select or poll has indicated that the file is writable,
# we can write up to _PIPE_BUF bytes without risk of blocking.
# POSIX defines PIPE_BUF as >= 512.
# Pystachy port: select.PIPE_BUF's value, which CPython reads
_PIPE_BUF = 4096 if sys.platform == "linux" else 512

_time = time.monotonic


def _handle(stream: Any) -> int | None:
    # Pystachy port: a stdin, stdout or stderr argument as Popen takes it, by its type: None, an
    # int, or the file descriptor of a file
    if stream is None:
        return None
    if isinstance(stream, int):
        return stream
    return stream.fileno()


def _typed_text(text: Any, universal_newlines: Any, encoding: Any, errors: Any) -> bool:
    # Pystachy port: text mode as CPython decides it from the values, checked against how it was
    # compiled, which the types of the four decided
    if (text is not None and universal_newlines is not None
        and bool(universal_newlines) != bool(text)):
        raise SubprocessError('Cannot disambiguate when both text '
                              'and universal_newlines are supplied but '
                              'different. Pass one or the other.')
    if text is None and universal_newlines is None and encoding is None and errors is None:
        return False
    mode = False
    if text is not None:
        mode = mode or bool(text)
    if universal_newlines is not None:
        mode = mode or bool(universal_newlines)
    if encoding is not None:
        mode = mode or encoding != ""
    if errors is not None:
        mode = mode or errors != ""
    if not mode:
        raise ValueError("a call that passes text, universal_newlines, encoding or errors is compiled to "
                         "return str, and none of them is true: leave them out for bytes")
    return True


def _encoding_of(encoding: Any) -> str:
    # Pystachy port: the encoding of the io.TextIOWrapper that CPython makes of a pipe
    if encoding is None:
        return __pys_proc_encoding()
    return encoding


def _errors_of(errors: Any) -> str:
    if errors is None:
        return "strict"
    return errors


def _translate_newlines(data: bytes, encoding: str, errors: str) -> str:
    text = data.decode(encoding, errors)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _result(data: bytes | None, text: Any, universal_newlines: Any, encoding: Any, errors: Any) -> Any:
    # Pystachy port: what run() returns of a pipe's data: the bytes, or in text mode their text;
    # None for a stream that is not a pipe
    if text is None and universal_newlines is None and encoding is None and errors is None:
        return data
    if data is None:
        return None
    return _translate_newlines(data, _encoding_of(encoding), _errors_of(errors))


def _empty_input(text: Any, universal_newlines: Any, encoding: Any, errors: Any) -> Any:
    if text is None and universal_newlines is None and encoding is None and errors is None:
        return b''
    return ''


def _input_bytes(input: Any, text: Any, universal_newlines: Any, encoding: Any, errors: Any) -> bytes | None:
    # Pystachy port: the bytes to write of run()'s input: bytes, or in text mode a str
    if input is None:
        return None
    if text is None and universal_newlines is None and encoding is None and errors is None:
        return input
    return input.encode(_encoding_of(encoding), _errors_of(errors))


def _output_bytes(value: Any) -> bytes | None:
    # Pystachy port: a CompletedProcess's stdout or stderr as CalledProcessError holds it
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    return value.encode()


def _checked(value: Any) -> Any:
    # Pystachy port: check_output()'s result, which is the data of a pipe
    if value is None:
        raise SubprocessError("check_output() did not capture stdout")
    return value


def _exec_path(env: dict[str, str] | None) -> list[str]:
    # os.get_exec_path(env): the directories to search for a program
    path_list: str | None = None
    if env is None:
        path_list = os.environ.get('PATH')
    else:
        path_list = env.get('PATH')
    if path_list is None:
        path_list = '/bin:/usr/bin'
    return path_list.split(':')


def call(args: str | list[str], bufsize: int = -1, *, stdin: Any = None, stdout: Any = None, stderr: Any = None,
         close_fds: bool = True, shell: bool = False, cwd: str | None = None, env: dict[str, str] | None = None,
         universal_newlines: Any = None, restore_signals: bool = True, start_new_session: bool = False,
         encoding: Any = None, errors: Any = None, text: Any = None,
         timeout: int | float | None = None) -> int:
    """Run command with arguments.  Wait for command to complete or
    for timeout seconds, then return the returncode attribute.

    The arguments are the same as for the Popen constructor.  Example:

    retcode = call(["ls", "-l"])
    """
    # Pystachy port: text mode makes no difference to a call that returns the status, but which
    # of its arguments CPython refuses
    _typed_text(text, universal_newlines, encoding, errors)
    with Popen(args, bufsize, stdin=_handle(stdin), stdout=_handle(stdout), stderr=_handle(stderr),
               close_fds=close_fds, shell=shell, cwd=cwd, env=env, restore_signals=restore_signals,
               start_new_session=start_new_session) as p:
        try:
            return p.wait(timeout=timeout)
        except BaseException:  # Including KeyboardInterrupt, wait handled that.
            p.kill()
            raise


def check_call(args: str | list[str], bufsize: int = -1, *, stdin: Any = None, stdout: Any = None, stderr: Any = None,
               close_fds: bool = True, shell: bool = False, cwd: str | None = None, env: dict[str, str] | None = None,
               universal_newlines: Any = None, restore_signals: bool = True, start_new_session: bool = False,
               encoding: Any = None, errors: Any = None, text: Any = None,
               timeout: int | float | None = None) -> int:
    """Run command with arguments.  Wait for command to complete.  If
    the exit code was zero then return, otherwise raise
    CalledProcessError.  The CalledProcessError object will have the
    return code in the returncode attribute.

    The arguments are the same as for the call function.  Example:

    check_call(["ls", "-l"])
    """
    retcode = call(args, bufsize, stdin=stdin, stdout=stdout, stderr=stderr, close_fds=close_fds, shell=shell,
                   cwd=cwd, env=env, universal_newlines=universal_newlines, restore_signals=restore_signals,
                   start_new_session=start_new_session, encoding=encoding, errors=errors, text=text,
                   timeout=timeout)
    if retcode:
        raise CalledProcessError(retcode, args)
    return 0


def check_output(args: str | list[str], bufsize: int = -1, *, stdin: Any = None, stderr: Any = None,
                 close_fds: bool = True, shell: bool = False, cwd: str | None = None,
                 env: dict[str, str] | None = None, universal_newlines: Any = None, restore_signals: bool = True,
                 start_new_session: bool = False, encoding: Any = None, errors: Any = None, text: Any = None,
                 input: Any = False, timeout: int | float | None = None) -> Any:
    r"""Run command with arguments and return its output.

    If the exit code was non-zero it raises a CalledProcessError.  The
    CalledProcessError object will have the return code in the returncode
    attribute and output in the output attribute.

    The arguments are the same as for the Popen constructor.  Example:

    >>> check_output(["ls", "-l", "/dev/null"])
    b'crw-rw-rw- 1 root root 1, 3 Oct 18  2007 /dev/null\n'

    The stdout argument is not allowed as it is used internally.
    To capture standard error in the result, use stderr=STDOUT.

    >>> check_output(["/bin/sh", "-c",
    ...               "ls -l non_existent_file ; exit 0"],
    ...              stderr=STDOUT)
    b'ls: non_existent_file: No such file or directory\n'

    There is an additional optional argument, "input", allowing you to
    pass a string to the subprocess's stdin.  If you use this argument
    you may not also use the Popen constructor's "stdin" argument, as
    it too will be used internally.  Example:

    >>> check_output(["sed", "-e", "s/foo/bar/"],
    ...              input=b"when in the course of fooman events\n")
    b'when in the course of barman events\n'

    By default, all communication is in bytes, and therefore any "input"
    should be bytes, and the return value will be bytes.  If in text mode,
    any "input" should be a string, and the return value will be a string
    decoded according to locale encoding, or by "encoding" if set. Text mode
    is triggered by setting any of text, encoding, errors or universal_newlines.
    """
    # Pystachy port: stdout and check are no parameters, where CPython raises ValueError for them;
    # input's default is a bool, for a call that passes none, which is not one of input=None
    if isinstance(input, bool):
        return _checked(run(args, bufsize, stdin=stdin, stdout=PIPE, stderr=stderr, close_fds=close_fds,
                            shell=shell, cwd=cwd, env=env, universal_newlines=universal_newlines,
                            restore_signals=restore_signals, start_new_session=start_new_session,
                            encoding=encoding, errors=errors, text=text, timeout=timeout, check=True).stdout)
    if input is None:
        # Explicitly passing input=None was previously equivalent to passing an
        # empty string. That is maintained here for backwards compatibility.
        return _checked(run(args, bufsize, stdin=stdin, stdout=PIPE, stderr=stderr, close_fds=close_fds,
                            shell=shell, cwd=cwd, env=env, universal_newlines=universal_newlines,
                            restore_signals=restore_signals, start_new_session=start_new_session,
                            encoding=encoding, errors=errors, text=text,
                            input=_empty_input(text, universal_newlines, encoding, errors), timeout=timeout,
                            check=True).stdout)
    return _checked(run(args, bufsize, stdin=stdin, stdout=PIPE, stderr=stderr, close_fds=close_fds,
                        shell=shell, cwd=cwd, env=env, universal_newlines=universal_newlines,
                        restore_signals=restore_signals, start_new_session=start_new_session,
                        encoding=encoding, errors=errors, text=text, input=input, timeout=timeout,
                        check=True).stdout)


_T = TypeVar("_T")
# Pystachy port: a stdout or stderr that is left out is a None of the type that holds bytes
_NOT_CAPTURED: bytes | None = None


class CompletedProcess(Generic[_T]):
    """A process that has finished running.

    This is returned by run().

    Attributes:
      args: The list or str args passed to run().
      returncode: The exit code of the process, negative for signals.
      stdout: The standard output (None if not captured).
      stderr: The standard error (None if not captured).
    """
    # Pystachy port: generic in the type of stdout and stderr, bytes or str, which CPython's
    # __class_getitem__ lets an annotation name (CompletedProcess[str]): the arguments say which
    def __init__(self, args: str | list[str], returncode: int, stdout: _T | None = _NOT_CAPTURED,
                 stderr: _T | None = _NOT_CAPTURED) -> None:
        self.args = args
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        # Pystachy port: what run() captured before it decoded it, for check_returncode()
        self._stdout_bytes: bytes | None = None
        self._stderr_bytes: bytes | None = None

    def __repr__(self) -> str:
        args = ['args={!r}'.format(self.args),
                'returncode={!r}'.format(self.returncode)]
        if self.stdout is not None:
            args.append('stdout={!r}'.format(self.stdout))
        if self.stderr is not None:
            args.append('stderr={!r}'.format(self.stderr))
        return "{}({})".format(type(self).__name__, ', '.join(args))

    def check_returncode(self) -> None:
        """Raise CalledProcessError if the exit code is non-zero."""
        if self.returncode:
            # Pystachy port: the exception's bytes (CalledProcessError)
            out = self._stdout_bytes
            err = self._stderr_bytes
            raise CalledProcessError(self.returncode, self.args,
                                     out if out is not None else _output_bytes(self.stdout),
                                     err if err is not None else _output_bytes(self.stderr))


def run(args: str | list[str], bufsize: int = -1, *, stdin: Any = None, stdout: Any = None, stderr: Any = None,
        close_fds: bool = True, shell: bool = False, cwd: str | None = None, env: dict[str, str] | None = None,
        universal_newlines: Any = None, restore_signals: bool = True, start_new_session: bool = False,
        encoding: Any = None, errors: Any = None, text: Any = None,
        input: Any = None, capture_output: bool = False, timeout: int | float | None = None,
        check: bool = False) -> Any:
    """Run command with arguments and return a CompletedProcess instance.

    The returned instance will have attributes args, returncode, stdout and
    stderr. By default, stdout and stderr are not captured, and those attributes
    will be None. Pass stdout=PIPE and/or stderr=PIPE in order to capture them,
    or pass capture_output=True to capture both.

    If check is True and the exit code was non-zero, it raises a
    CalledProcessError. The CalledProcessError object will have the return code
    in the returncode attribute, and output & stderr attributes if those streams
    were captured.

    If timeout (seconds) is given and the process takes too long,
     a TimeoutExpired exception will be raised.

    There is an optional argument "input", allowing you to
    pass bytes or a string to the subprocess's stdin.  If you use this argument
    you may not also use the Popen constructor's "stdin" argument, as
    it will be used internally.

    By default, all communication is in bytes, and therefore any "input" should
    be bytes, and the stdout and stderr will be bytes. If in text mode, any
    "input" should be a string, and stdout and stderr will be strings decoded
    according to locale encoding, or by "encoding" if set. Text mode is
    triggered by setting any of text, encoding, errors or universal_newlines.

    The other arguments are the same as for the Popen constructor.
    """
    # Pystachy port: text mode is run()'s, around a Popen whose pipes carry bytes: it encodes
    # the input first, and decodes what was captured once the child has ended, as CPython's
    # communicate() does. The three streams are None or ints (_handle).
    _typed_text(text, universal_newlines, encoding, errors)
    child_stdin = _handle(stdin)
    child_stdout = _handle(stdout)
    child_stderr = _handle(stderr)
    data = _input_bytes(input, text, universal_newlines, encoding, errors)
    if data is not None:
        if child_stdin is not None:
            raise ValueError('stdin and input arguments may not both be used.')
        child_stdin = PIPE

    if capture_output:
        if child_stdout is not None or child_stderr is not None:
            raise ValueError('stdout and stderr arguments may not be used '
                             'with capture_output.')
        child_stdout = PIPE
        child_stderr = PIPE

    with Popen(args, bufsize, stdin=child_stdin, stdout=child_stdout, stderr=child_stderr, close_fds=close_fds,
               shell=shell, cwd=cwd, env=env, restore_signals=restore_signals,
               start_new_session=start_new_session) as process:
        try:
            out, err = process.communicate(data, timeout=timeout)
            stdout_result = _result(out, text, universal_newlines, encoding, errors)
            stderr_result = _result(err, text, universal_newlines, encoding, errors)
        except TimeoutExpired:
            process.kill()
            # POSIX _communicate already populated the output so
            # far into the TimeoutExpired exception.
            process.wait()
            raise
        except BaseException:  # Including KeyboardInterrupt, communicate handled that.
            process.kill()
            # We don't call process.wait() as .__exit__ does that for us.
            raise
        retcode = process.wait()
        if check and retcode:
            raise CalledProcessError(retcode, process.args,
                                     output=out, stderr=err)
        done = CompletedProcess(process.args, retcode, stdout_result, stderr_result)
        done._stdout_bytes = out
        done._stderr_bytes = err
        return done


def list2cmdline(seq: list[str]) -> str:
    """
    Translate a sequence of arguments into a command line
    string, using the same rules as the MS C runtime:

    1) Arguments are delimited by white space, which is either a
       space or a tab.

    2) A string surrounded by double quotation marks is
       interpreted as a single argument, regardless of white space
       contained within.  A quoted string can be embedded in an
       argument.

    3) A double quotation mark preceded by a backslash is
       interpreted as a literal double quotation mark.

    4) Backslashes are interpreted literally, unless they
       immediately precede a double quotation mark.

    5) If backslashes immediately precede a double quotation mark,
       every pair of backslashes is interpreted as a literal
       backslash.  If the number of backslashes is odd, the last
       backslash escapes the next double quotation mark as
       described in rule 3.
    """

    # See
    # http://msdn.microsoft.com/en-us/library/17w5ykft.aspx
    # or search http://msdn.microsoft.com for
    # "Parsing C++ Command-Line Arguments"
    result: list[str] = []
    needquote = False
    for arg in seq:
        bs_buf: list[str] = []

        # Add a space to separate this argument from the others
        if result:
            result.append(' ')

        needquote = (" " in arg) or ("\t" in arg) or not arg
        if needquote:
            result.append('"')

        for c in arg:
            if c == '\\':
                # Don't know if we need to double yet.
                bs_buf.append(c)
            elif c == '"':
                # Double backslashes.
                result.append('\\' * len(bs_buf)*2)
                bs_buf = []
                result.append('\\"')
            else:
                # Normal char
                if bs_buf:
                    result.extend(bs_buf)
                    bs_buf = []
                result.append(c)

        # Add remaining backslashes, if any.
        if bs_buf:
            result.extend(bs_buf)

        if needquote:
            result.extend(bs_buf)
            result.append('"')

    return ''.join(result)


# Various tools for executing commands and looking at their output and status.
#

def getstatusoutput(cmd: str | list[str], *, encoding: str | None = None,
                    errors: str | None = None) -> tuple[int, str]:
    """Return (exitcode, output) of executing cmd in a shell.

    Execute the string 'cmd' in a shell with 'check_output' and
    return a 2-tuple (status, output). The locale encoding is used
    to decode the output and process newlines.

    A trailing newline is stripped from the output.
    The exit status for the command can be interpreted
    according to the rules for the function 'wait'. Example:

    >>> import subprocess
    >>> subprocess.getstatusoutput('ls /bin/ls')
    (0, '/bin/ls')
    >>> subprocess.getstatusoutput('cat /bin/junk')
    (1, 'cat: /bin/junk: No such file or directory')
    >>> subprocess.getstatusoutput('/bin/junk')
    (127, 'sh: /bin/junk: not found')
    >>> subprocess.getstatusoutput('/bin/kill $$')
    (-15, '')
    """
    # Pystachy port: run() without check, as the CalledProcessError of check_output() holds the
    # output of a command that failed as bytes here
    done = run(cmd, shell=True, text=True, stdout=PIPE, stderr=STDOUT,
               encoding=encoding, errors=errors)
    data = _checked(done.stdout)
    exitcode = done.returncode
    if data[-1:] == '\n':
        data = data[:-1]
    return exitcode, data


def getoutput(cmd: str | list[str], *, encoding: str | None = None, errors: str | None = None) -> str:
    """Return output (stdout or stderr) of executing cmd in a shell.

    Like getstatusoutput(), except the exit status is ignored and the return
    value is a string containing the command's output.  Example:

    >>> import subprocess
    >>> subprocess.getoutput('ls /bin/ls')
    '/bin/ls'
    """
    return getstatusoutput(cmd, encoding=encoding, errors=errors)[1]


class Popen:
    """ Execute a child program in a new process.

    For a complete description of the arguments see the Python documentation.

    Arguments:
      args: A string, or a sequence of program arguments.

      bufsize: supplied as the buffering argument to the open() function when
          creating the stdin/stdout/stderr pipe file objects

      stdin, stdout and stderr: These specify the executed programs' standard
          input, standard output and standard error file handles, respectively.

      close_fds: Controls closing or inheriting of file descriptors.

      shell: If true, the command will be executed through the shell.

      cwd: Sets the current directory before the child is executed.

      env: Defines the environment variables for the new process.

      restore_signals (POSIX only)

      start_new_session (POSIX only)

    Attributes:
        args, pid, returncode
    """
    # Pystachy port: the parameters past bufsize are keyword-only, as not all of CPython's are
    # here: a call that passes them by position would give them to others. There are no text,
    # universal_newlines, encoding and errors (the pipes carry bytes), no executable, preexec_fn,
    # pass_fds, user, group, extra_groups, umask, pipesize and process_group, and no startupinfo
    # and creationflags of Windows. stdin, stdout and stderr are None or an int: a file's is its
    # fileno().
    def __init__(self, args: str | list[str], bufsize: int = -1, *,
                 stdin: int | None = None, stdout: int | None = None, stderr: int | None = None,
                 close_fds: bool = True, shell: bool = False, cwd: str | None = None,
                 env: dict[str, str] | None = None,
                 restore_signals: bool = True, start_new_session: bool = False) -> None:
        """Create new Popen instance."""
        # Held while anything is calling waitpid before returncode has been
        # updated to prevent clobbering returncode if wait() or poll() are
        # called from multiple threads at once.  After acquiring the lock,
        # code must re-check self.returncode to see if another thread just
        # finished a waitpid() call.
        # Pystachy port: no lock, as a program waits for its children on one thread
        self._communication_started = False
        self._closed_child_pipe_fds = False

        if stdout == STDOUT:
            raise ValueError("STDOUT can only be used for stderr")

        self.args = args
        self.pid = -1
        self.returncode: int | None = None

        # Input and output objects. The general principle is like
        # this:
        #
        # Parent                   Child
        # ------                   -----
        # p2cwrite   ---stdin--->  p2cread
        # c2pread    <--stdout---  c2pwrite
        # errread    <--stderr---  errwrite
        #
        # Pystachy port: the parent's ends are file descriptors, not files (-1: no pipe, or
        # closed), with the data that communicate() has read and has still to write
        self._p2cwrite = -1
        self._c2pread = -1
        self._errread = -1
        self._devnull = -1
        self._stdout_piped = False
        self._stderr_piped = False
        self._stdout_chunks: list[bytes] = []
        self._stderr_chunks: list[bytes] = []
        self._stdout_bytes: bytes | None = None
        self._stderr_bytes: bytes | None = None
        self._input: bytes | None = None
        self._input_offset = 0

        p2cread = -1
        c2pwrite = -1
        errwrite = -1
        try:
            # _get_handles(): Construct and return tuple with IO objects:
            # p2cread, p2cwrite, c2pread, c2pwrite, errread, errwrite
            if stdin is None:
                pass
            elif stdin == PIPE:
                ends = __pys_proc_pipe()
                p2cread = ends[0]
                self._p2cwrite = ends[1]
            elif stdin == DEVNULL:
                p2cread = self._get_devnull()
            else:
                p2cread = stdin

            if stdout is None:
                pass
            elif stdout == PIPE:
                ends = __pys_proc_pipe()
                self._c2pread = ends[0]
                c2pwrite = ends[1]
                self._stdout_piped = True
            elif stdout == DEVNULL:
                c2pwrite = self._get_devnull()
            else:
                c2pwrite = stdout

            if stderr is None:
                pass
            elif stderr == PIPE:
                ends = __pys_proc_pipe()
                self._errread = ends[0]
                errwrite = ends[1]
                self._stderr_piped = True
            elif stderr == STDOUT:
                if c2pwrite != -1:
                    errwrite = c2pwrite
                else: # child's stdout is not set, use parent's stdout
                    errwrite = 1
            elif stderr == DEVNULL:
                errwrite = self._get_devnull()
            else:
                errwrite = stderr

            self._execute_child(args, close_fds, cwd, env, shell, p2cread, c2pwrite, errwrite,
                                restore_signals, start_new_session)
        except BaseException:
            # Cleanup if the child failed starting.
            self._close_parent_fds()

            if not self._closed_child_pipe_fds:
                to_close: list[int] = []
                if stdin == PIPE and p2cread != -1:
                    to_close.append(p2cread)
                if stdout == PIPE and c2pwrite != -1:
                    to_close.append(c2pwrite)
                if stderr == PIPE and errwrite != -1:
                    to_close.append(errwrite)
                if self._devnull != -1:
                    to_close.append(self._devnull)
                for fd in to_close:
                    try:
                        __pys_proc_close(fd)
                    except OSError:
                        pass

            raise

    __class_getitem__ = classmethod(GenericAlias)

    def __enter__(self) -> "Popen":
        return self

    def __exit__(self, exc_type, value, traceback) -> None:
        self._close_parent_fds()
        # Wait for the process to terminate, to avoid zombies.
        self.wait()

    def _close_parent_fds(self) -> None:
        # Pystachy port: what closes the stdin, stdout and stderr files of CPython's Popen
        for fd in (self._p2cwrite, self._c2pread, self._errread):
            if fd != -1:
                try:
                    __pys_proc_close(fd)
                except OSError:
                    pass  # Ignore EBADF or other errors.
        self._p2cwrite = -1
        self._c2pread = -1
        self._errread = -1

    def _get_devnull(self) -> int:
        if self._devnull == -1:
            self._devnull = __pys_proc_devnull()
        return self._devnull

    def communicate(self, input: bytes | None = None,
                    timeout: int | float | None = None) -> tuple[bytes | None, bytes | None]:
        """Interact with process: Send data to stdin and close it.
        Read data from stdout and stderr, until end-of-file is
        reached.  Wait for process to terminate.

        The optional "input" argument should be data to be sent to the
        child process, or None, if no data should be sent to the child.
        communicate() returns a tuple (stdout, stderr).

        By default, all communication is in bytes, and therefore any
        "input" should be bytes, and the (stdout, stderr) will be bytes.
        """
        if self._communication_started and input:
            raise ValueError("Cannot send input after starting communication")

        # Pystachy port: without CPython's shortcut for one pipe and no timeout, which reads or
        # writes that pipe's file: the loop below does the same of its descriptor
        endtime: float | None = None
        if timeout is not None:
            endtime = _time() + float(timeout)

        try:
            self._communicate(input, endtime, timeout)
        finally:
            self._communication_started = True

        self.wait(timeout=self._remaining_time(endtime))

        return (self._stdout_bytes, self._stderr_bytes)

    def poll(self) -> int | None:
        """Check if child process has terminated. Set and return returncode
        attribute."""
        return self._internal_poll()

    def _remaining_time(self, endtime: float | None) -> float | None:
        """Convenience for _communicate when computing timeouts."""
        if endtime is None:
            return None
        else:
            return endtime - _time()

    def _check_timeout(self, endtime: float | None, orig_timeout: int | float | None,
                       skip_check_and_raise: bool = False) -> None:
        """Convenience for checking if a timeout has expired."""
        if endtime is None:
            return
        if skip_check_and_raise or _time() > endtime:
            raise TimeoutExpired(
                    self.args, orig_timeout,
                    output=b''.join(self._stdout_chunks) if self._stdout_chunks else None,
                    stderr=b''.join(self._stderr_chunks) if self._stderr_chunks else None)

    def wait(self, timeout: int | float | None = None) -> int:
        """Wait for child process to terminate; returns self.returncode."""
        # Pystachy port: without CPython's handling of KeyboardInterrupt, which a program does
        # not catch here: Ctrl-C ends it
        return self._wait(timeout)

    def _execute_child(self, args: str | list[str], close_fds: bool, cwd: str | None,
                       env: dict[str, str] | None, shell: bool, p2cread: int, c2pwrite: int, errwrite: int,
                       restore_signals: bool, start_new_session: bool) -> None:
        """Execute program (POSIX version)"""

        argv: list[str] = []
        if isinstance(args, str):
            argv = [args]
        else:
            argv = list(args)

        if shell:
            # On Android the default shell is at '/system/bin/sh'.
            argv = ['/bin/sh', "-c"] + argv

        executable = argv[0]

        # We must avoid complex work that could involve
        # malloc or free in the child process to avoid
        # potential deadlocks, thus we do all this here.
        # and pass it to fork_exec()

        env_list: list[str] = []
        if env is not None:
            for k, v in env.items():
                if '=' in k:
                    raise ValueError("illegal environment variable name")
                env_list.append(k + '=' + v)
        executable_list: list[str] = []
        if os.path.dirname(executable):
            executable_list = [executable]
        else:
            # This matches the behavior of os._execvpe().
            executable_list = [os.path.join(dir, executable) for dir in _exec_path(env)]
        # Pystachy port: the child's failure to become the program comes back from the primitive
        # as the exception that CPython makes of what it reads from a pipe
        flags = (1 if close_fds else 0) | (2 if restore_signals else 0) | (4 if start_new_session else 0)
        if env is not None:
            flags |= 8
        if cwd is not None:
            flags |= 16
        self.pid = __pys_proc_fork_exec(argv, executable_list, env_list, cwd if cwd is not None else "",
                                        p2cread, c2pwrite, errwrite, flags)

        # _close_pipe_fds()
        if p2cread != -1 and self._p2cwrite != -1 and p2cread != self._devnull:
            __pys_proc_close(p2cread)
        if c2pwrite != -1 and self._c2pread != -1 and c2pwrite != self._devnull:
            __pys_proc_close(c2pwrite)
        if errwrite != -1 and self._errread != -1 and errwrite != self._devnull:
            __pys_proc_close(errwrite)

        if self._devnull != -1:
            __pys_proc_close(self._devnull)
            self._devnull = -1

        # Prevent a double close of these handles/fds from __init__ on error.
        self._closed_child_pipe_fds = True

    def _internal_poll(self) -> int | None:
        """Check if child process has terminated.  Returns returncode
        attribute.
        """
        if self.returncode is None:
            # Pystachy port: the primitive's 0 for a child that is not this process's to wait
            # for, which CPython makes of waitpid()'s ECHILD
            sts = __pys_proc_wait(self.pid, 1)
            if sts != _RUNNING:
                self.returncode = sts
        return self.returncode

    def _wait(self, timeout: int | float | None) -> int:
        """Internal implementation of wait() on POSIX."""
        code = self.returncode
        if code is not None:
            return code

        if timeout is not None:
            endtime = _time() + float(timeout)
            # Enter a busy loop if we have a timeout.  This busy loop was
            # cribbed from Lib/threading.py in Thread.wait() at r71065.
            delay = 0.0005 # 500 us -> initial delay of 1 ms
            while True:
                sts = __pys_proc_wait(self.pid, 1)
                if sts != _RUNNING:
                    self.returncode = sts
                    return sts
                remaining = endtime - _time()
                if remaining <= 0:
                    raise TimeoutExpired(self.args, timeout)
                delay = min(delay * 2, remaining, .05)
                time.sleep(delay)
        else:
            sts = _RUNNING
            while sts == _RUNNING:
                # Check the pid and loop as waitpid has been known to
                # return 0 even without WNOHANG in odd situations.
                # http://bugs.python.org/issue14396.
                sts = __pys_proc_wait(self.pid, 0)
            self.returncode = sts
            return sts

    def _communicate(self, input: bytes | None, endtime: float | None,
                     orig_timeout: int | float | None) -> None:
        if self._p2cwrite != -1 and not self._communication_started:
            if not input:
                self._close_stdin()

        # _save_input()
        # This method is called from the _communicate_with_*() methods
        # so that if we time out while communicating, we can continue
        # sending input if we retry.
        if self._p2cwrite != -1 and self._input is None:
            self._input_offset = 0
            self._input = input

        data = self._input
        while ((self._p2cwrite != -1 and data is not None and len(data) > 0)
               or self._c2pread != -1 or self._errread != -1):
            timeout = self._remaining_time(endtime)
            if timeout is not None and timeout < 0:
                self._check_timeout(endtime, orig_timeout,
                                    skip_check_and_raise=True)
                raise RuntimeError(  # Impossible :)
                    '_check_timeout(..., skip_check_and_raise=True) '
                    'failed to raise TimeoutExpired.')

            writing = self._p2cwrite if data is not None and len(data) > 0 else -1
            ready = __pys_proc_ready(self._c2pread, self._errread, writing,
                                     timeout if timeout is not None else -1.0)
            self._check_timeout(endtime, orig_timeout)

            if ready & 4 and data is not None:
                try:
                    self._input_offset += __pys_proc_write(self._p2cwrite, data, self._input_offset, _PIPE_BUF)
                except BrokenPipeError:
                    self._close_stdin()
                else:
                    if self._input_offset >= len(data):
                        self._close_stdin()
            if ready & 1:
                chunk = __pys_proc_read(self._c2pread, 32768)
                if not chunk:
                    __pys_proc_close(self._c2pread)
                    self._c2pread = -1
                self._stdout_chunks.append(chunk)
            if ready & 2:
                chunk = __pys_proc_read(self._errread, 32768)
                if not chunk:
                    __pys_proc_close(self._errread)
                    self._errread = -1
                self._stderr_chunks.append(chunk)

        try:
            self.wait(timeout=self._remaining_time(endtime))
        except TimeoutExpired as exc:
            exc.timeout = orig_timeout
            raise

        # All data exchanged.  Translate lists into strings.
        if self._stdout_piped:
            self._stdout_bytes = b''.join(self._stdout_chunks)
        if self._stderr_piped:
            self._stderr_bytes = b''.join(self._stderr_chunks)

    def _close_stdin(self) -> None:
        # Pystachy port: stdin.close(), whose BrokenPipeError communicate() must ignore
        if self._p2cwrite != -1:
            try:
                __pys_proc_close(self._p2cwrite)
            except OSError:
                pass
            self._p2cwrite = -1

    def send_signal(self, sig: int) -> None:
        """Send a signal to the process."""
        # bpo-38630: Polling reduces the risk of sending a signal to the
        # wrong process if the process completed, the Popen.returncode
        # attribute is still None, and the pid has been reassigned
        # (recycled) to a new different process. This race condition can
        # happens in two cases.
        #
        # Case 1. Thread A calls Popen.poll(), thread B calls
        # Popen.send_signal(). In thread A, waitpid() succeed and returns
        # the exit status. Thread B calls kill() because poll() in thread A
        # did not set returncode yet. Calling poll() in thread B prevents
        # the race condition thanks to Popen._waitpid_lock.
        #
        # Case 2. waitpid(pid, 0) has been called directly, without
        # using Popen methods: returncode is still None is this case.
        # Calling Popen.poll() will set returncode to a default value,
        # since waitpid() fails with ProcessLookupError.
        self.poll()
        if self.returncode is not None:
            # Skip signalling a process that we know has already died.
            return

        # The race condition can still happen if the race condition
        # described above happens between the returncode test
        # and the kill() call.
        try:
            __pys_proc_kill(self.pid, sig)
        except ProcessLookupError:
            # Suppress the race condition error; bpo-40550.
            pass

    def terminate(self) -> None:
        """Terminate the process with SIGTERM
        """
        self.send_signal(15)

    def kill(self) -> None:
        """Kill the process with SIGKILL
        """
        self.send_signal(9)


# Pystachy port: __pys_proc_wait()'s result for a child that has not ended (no exit status is)
_RUNNING = 256
