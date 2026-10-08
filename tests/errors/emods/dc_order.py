from dataclasses import dataclass
from typing import Callable


@dataclass
class Job:
    retries: int = 3
    run: Callable
