# error: 'match' statements are not supported
# lib/statistics's kde() stays uncompiled (lib/README.md): it picks its kernel in a match statement,
# and returns closures that it sets a __doc__ on
import statistics

print(statistics.kde([1.0, 2.0, 4.0], h=1.5)(2.0))
