# Execute the compiler's own summary solver with both JIT/AOT and both hosts.
from src.pystachy_compiler.ircheck import EffectSummaries
from src.pystachy_compiler.specs import FXALL, FXBIT

summaries = EffectSummaries()
calls: list[list[int]] = [[j + 1] for j in range(23)] + [[], []]
direct = [0] * 23 + [FXBIT["wD"], 0]
summaries.update(direct, calls)
print(summaries.fx == [FXBIT["wD"]] * 24 + [0], summaries.edge_visits)
summaries.update(direct, calls)
print(summaries.reused, summaries.edge_visits)
direct[23] = FXBIT["rL"]
summaries.update(direct, calls)
print(summaries.fx == [FXBIT["rL"]] * 24 + [0], summaries.reused, summaries.edge_visits)
summaries.update([0, 0, FXBIT["I"], FXALL], [[1], [2], [1], []])
print(summaries.fx == [FXBIT["I"]] * 3 + [FXALL])
summaries.update([0, 0, 0, FXALL], [[1], [2], [1], []])
print(summaries.fx == [0, 0, 0, FXALL], summaries.reused)
summaries.update([0, 0, 0, FXALL], [[1], [2], [1, 3], []])
print(summaries.fx == [FXALL] * 4, summaries.reused)
summaries.update([0, 0, 0, FXALL], [[1], [2], [1], []])
print(summaries.fx == [0, 0, 0, FXALL], summaries.reused)
