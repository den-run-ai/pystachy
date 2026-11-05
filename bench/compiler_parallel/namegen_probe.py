"""Original consumer of the unchanged, separately supplied mypyc name generator.

Source pin and SHA-256 are recorded by llvm_partitions.py. This fixture does not
vendor upstream code. Run with ROUNDS (default 2000); stdout is deterministic.
Each round constructs a fresh compilation group, mixes known and fresh module
names, reuses translations, and checks both abbreviated and separate names.
"""
import sys

from namegen import NameGenerator


FIXED_MODULES: list[str] = [
    "planner.search", "planner.agent", "executor.search", "executor.worker",
    "package.__main__", "package.nested.runtime", "other.nested.runtime",
]


def fingerprint(value: str, checksum: int) -> int:
    # Keep every intermediate inside int64; no process-randomized hash().
    for char in value:
        checksum = (checksum * 131 + ord(char)) % 1000000007
    return (checksum * 131 + 10) % 1000000007


def run(rounds: int) -> int:
    checksum = 0
    for step in range(rounds):
        group = FIXED_MODULES + [f"generated.part_{step}.api", f"generated.part_{step}.types"]
        generator = NameGenerator([group], separate=step % 2 != 0)
        for module in group:
            first = generator.private_name(module, "Node.visit")
            again = generator.private_name(module, "Node.visit")
            escaped = generator.private_name(module, "Node___visit")
            fresh = generator.private_name(module, f"Node.field_{step}")
            module_only = generator.private_name(module)
            if first != again or first == escaped:
                raise ValueError("translation reuse or escaping changed")
            for value in [first, again, escaped, fresh, module_only]:
                checksum = fingerprint(value, checksum)
            if step < 2:
                print("witness", step, module, [first, again, escaped, fresh, module_only])
        # Uncompiled modules and names without a module use different prefixes.
        for module in ["vendor.plugin", f"vendor.fresh_{step}", ""]:
            value = generator.private_name(module, "Helper.call")
            checksum = fingerprint(value, checksum)
            if step < 2:
                print("external", step, module, value)
    return checksum


rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
if rounds < 2:
    raise ValueError("at least two rounds are needed to check both naming modes")
print("rounds", rounds)
print("checksum", run(rounds))
