# concurrent.futures as mypy's build.py uses it (mypy 2.4.1, BuildManager.parse_all): a bound
# method that returns None is submitted with one argument for each state, the futures are kept
# in a list that starts empty, and wait(futures).done gives them back for result(), which raises
# what a call raised. The with statement shuts the executor down
from concurrent.futures import ThreadPoolExecutor, wait


class State:
    def __init__(self, id: str, source: str | None) -> None:
        self.id = id
        self.source = source
        self.needs_parse = True
        self.lines = -1

    def parse_file_inner(self, source: str | None, raw_data: bytes | None = None) -> None:
        if source is None:
            raise FileNotFoundError("no source for " + self.id)
        self.lines = source.count("\n")


class BuildManager:
    def __init__(self, num_workers: int) -> None:
        self.num_workers = num_workers
        self.ast_cache: dict[str, int] = {"cached": 7}

    def parse_all(self, states: list[State]) -> tuple[list[State], set[State]]:
        futures = []
        parallel_parsed_states: list[State] = []
        parallel_parsed_states_set: set[State] = set()
        available_threads = max(4, self.num_workers)
        with ThreadPoolExecutor(max_workers=min(available_threads, 8)) as executor:
            for state in states:
                state.needs_parse = False
                if state.id not in self.ast_cache:
                    futures.append(executor.submit(state.parse_file_inner, state.source))
                    parallel_parsed_states.append(state)
                    parallel_parsed_states_set.add(state)
                else:
                    state.lines = self.ast_cache[state.id]

            for fut in wait(futures).done:
                fut.result()

        return parallel_parsed_states, parallel_parsed_states_set


manager = BuildManager(2)
states = [State("a", "x = 1\n"), State("cached", None), State("b", "import a\n\nprint(a.x)\n")]
parsed, parsed_set = manager.parse_all(states)
print([s.id for s in parsed], len(parsed_set), states[1] in parsed_set)
print([(s.id, s.lines, s.needs_parse) for s in states])
print(manager.parse_all([State("cached", None)]))
try:
    manager.parse_all([State("c", "pass\n"), State("missing", None)])
except FileNotFoundError as e:
    print("FileNotFoundError:", e)
