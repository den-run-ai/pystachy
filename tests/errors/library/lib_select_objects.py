# error: expected int, got FD
import select


class FD:
    def fileno(self) -> int:
        return 0


select.select([FD()], [], [], 0)
