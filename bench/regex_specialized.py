"""Recurring date regex: fair VM, portable adapter, residual and concrete controls.

Generate regex_date_generated.py with tools/regex_specialize.py, then run under
CPython or compile this program. check covers held-out strings, flag/pattern
misses, positions and Unicode fallback; bench times in-process CPU execution.
"""
import re
import sys
import time
import regex_date_generated as helper


DATE = re.compile(helper.SOURCE)
CORPUS = [
    'build 2026-10-14 released; retry 2027-01-09; invalid 2026-1-09 and x.',
    'tags: 1900-00-99 99999-12-34 1234-56-78 123-45-67 0000-00-00.',
    'no date in this paragraph; lots of text and digits 01234567890123456789.',
    '2026-10-142027-01-09!2027-02-29 invalid-calendar 2026-99-99.',
    'trace: ' + 'not-a-date 0123x45x67 ' * 20 + ' end 2042-11-22.',
]


def check() -> None:
    for string in CORPUS + ['', '2026-10-14', 'x2026-10-14x', '٢٠٢٦-١٠-١٤', 'é 2026-10-14 é']:
        for pos in [-3, 0, 1, 5, len(string), len(string) + 2]:
            for end in [-1, 0, 9, 10, len(string), len(string) + 2]:
                baseline = helper.findall_generic(DATE, string, pos, end)
                assert helper.findall_vm(DATE, string, pos, end) == baseline
                assert helper.findall_specialized(DATE, string, pos, end) == baseline
                assert helper.findall_concrete(DATE, string, pos, end) == baseline
    for alternate in [re.compile(r'(\d{4})/(\d{2})/(\d{2})'),
                      re.compile(helper.SOURCE, re.ASCII),
                      re.compile(r'(\d+)-(\d+)-(\d+)')]:
        assert not helper.compatible(alternate)
        for string in ['2026/10/14 2026-10-14', 'é ٢٠٢٦-١٠-١٤ 2026-10-14']:
            assert helper.findall_specialized(alternate, string) == helper.findall_generic(alternate, string)
    failed = False
    try:
        helper.findall_specialized(re.compile('(x)(y)'), 'xy')
    except ValueError:
        failed = True
    assert failed
    if hasattr(DATE, '_code'):
        # The port's Pattern bytecode is mutable; source/flags alone are insufficient.
        index = -1
        for i in range(len(DATE._code)):
            if DATE._code[i] == ord('-'):
                index = i
                break
        assert index >= 0
        saved = DATE._code[index]
        try:
            DATE._code[index] = ord('/')
            assert not helper.compatible(DATE)
            assert helper.findall_specialized(DATE, '2026/10-14 2026-10-14') == [('2026', '10', '14')]
        finally:
            DATE._code[index] = saved
    print('check ok')


def run(mode: str, repeats: int) -> int:
    checksum = 0
    for _ in range(repeats):
        for string in CORPUS:
            if mode == 'vm':
                rows = helper.findall_vm(DATE, string)
            elif mode == 'generic':
                rows = helper.findall_generic(DATE, string)
            elif mode == 'concrete':
                rows = helper.findall_concrete(DATE, string)
            else:
                rows = helper.findall_specialized(DATE, string)
            for year, month, day in rows:
                checksum += int(year) + int(month) + int(day)
    return checksum


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else 'bench'
    if mode == 'check':
        check()
        return
    repeats = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    if mode != 'bench':
        start = time.process_time()
        result = run(mode, repeats)
        print(mode, result, time.process_time() - start)
        return
    check()
    for name in ['vm', 'generic', 'specialized', 'concrete']:
        # Warm the shared decoder and exercise all guards before timed execution.
        expected = run(name, 1)
        times: list[float] = []
        result = 0
        for _ in range(5):
            start = time.process_time()
            result = run(name, repeats)
            times.append(time.process_time() - start)
        assert result == expected * repeats
        times.sort()
        print(name, result, times[2])


if __name__ == '__main__':
    main()
