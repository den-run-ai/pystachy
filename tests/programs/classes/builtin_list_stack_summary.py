# A list subclass that only adds methods, as traceback.StackSummary does: built by a class
# method that appends to a new object, iterated by its own methods, and used as the list it is
# by code that knows nothing of the class (len, indexing, slicing, sorted, join).


class FrameSummary:
    def __init__(self, filename: str, lineno: int, name: str, line: str) -> None:
        self.filename = filename
        self.lineno = lineno
        self.name = name
        self.line = line

    def __repr__(self) -> str:
        return "<FrameSummary file {}, line {} in {}>".format(self.filename, self.lineno, self.name)


class StackSummary(list):
    """A list of FrameSummary objects, representing a stack of frames."""

    @classmethod
    def from_list(klass, a_list: list[tuple[str, int, str, str]]) -> "StackSummary":
        result = StackSummary()
        for frame in a_list:
            filename, lineno, name, line = frame
            result.append(FrameSummary(filename, lineno, name, line))
        return result

    def format_frame_summary(self, frame_summary: FrameSummary) -> str:
        row = []
        row.append('  File "{}", line {}, in {}\n'.format(frame_summary.filename, frame_summary.lineno, frame_summary.name))
        if frame_summary.line:
            row.append("    {}\n".format(frame_summary.line.strip()))
        return "".join(row)

    def format(self) -> list[str]:
        result = []
        last_file = ""
        last_line = -1
        last_name = ""
        count = 0
        for frame_summary in self:
            formatted_frame = self.format_frame_summary(frame_summary)
            if last_file != frame_summary.filename or last_line != frame_summary.lineno or last_name != frame_summary.name:
                if count > 3:
                    count -= 3
                    result.append("  [Previous line repeated {} more time{}]\n".format(count, "s" if count > 1 else ""))
                last_file = frame_summary.filename
                last_line = frame_summary.lineno
                last_name = frame_summary.name
                count = 0
            count += 1
            if count > 3:
                continue
            result.append(formatted_frame)
        if count > 3:
            count -= 3
            result.append("  [Previous line repeated {} more time{}]\n".format(count, "s" if count > 1 else ""))
        return result


def lines_of(stack: StackSummary) -> list[int]:
    return [f.lineno for f in stack]


frames = [("a.py", 1, "main", "run()"), ("b.py", 20, "run", "  step(n)  ")]
frames += [("c.py", 7, "step", "step(n - 1)")] * 6
frames.append(("d.py", 3, "leaf", ""))
stack = StackSummary.from_list(frames)
print(len(stack), isinstance(stack, list), isinstance(stack, StackSummary), type(stack).__name__)
print("".join(stack.format()), end="")
print(stack[0], stack[-1])
print(lines_of(stack))
print([f.name for f in stack[1:4]], type(stack[1:4]).__name__)
print(sorted([f.lineno for f in stack], reverse=True)[:3])
last = stack.pop()
print(last.name, len(stack))
stack.reverse()
print(stack[0].name, stack[-1].name)
empty = StackSummary()
print(len(empty), bool(empty), bool(stack), empty.format())
empty.extend(stack[:2])
print(len(empty), empty == stack[:2], empty != stack, empty == stack)
