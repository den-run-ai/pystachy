# A module's global annotated as a dict (dict, Dict, Mapping or MutableMapping, qualified or
# quoted) whose value is a call of collections' defaultdict, OrderedDict or Counter, which derive
# from dict: the global holds the object the call makes, so a missing key calls its factory
import collections
import collections.abc
import typing
from collections import Counter, OrderedDict, defaultdict
from collections.abc import Mapping, MutableMapping
from typing import Dict

sub_code_map: dict[str, set[str]] = defaultdict(set)
sub_code_map["misc"].add("b")
sub_code_map["misc"].add("a")
counts: Dict[str, int] = defaultdict(int)
counts["x"] += 2
lists: typing.Dict[str, list[int]] = collections.defaultdict(list)
lists["k"].append(1)
module_map: Mapping[str, list[str]] = defaultdict(list)
module_map["m"].append("n")
mutable: MutableMapping[str, int] = defaultdict(lambda: 7)
qualified: collections.abc.Mapping[str, int] = defaultdict(int, {"q": 1})
quoted: "dict[str, int]" = defaultdict(int)
ordered: dict[str, int] = OrderedDict([("b", 2), ("a", 1)])
tally: dict[str, int] = Counter("abca")
print(sorted(sub_code_map["misc"]), counts, lists, module_map["m"], mutable["new"], len(mutable))
print(qualified["q"], qualified["missing"], quoted["z"], quoted)
print(ordered, list(ordered), tally["a"], tally["none"], len(tally))
print(isinstance(sub_code_map, dict), type(counts).__name__, type(ordered).__name__, type(tally).__name__)
