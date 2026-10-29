# pystachy: dynamic-any
import inert_scope

# No numeric value crosses the module boundary, but list search/equality still
# observes the shared NaN and must make the compiler discard the hint.
print(inert_scope.observes())
