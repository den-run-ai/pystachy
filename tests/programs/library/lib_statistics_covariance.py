# lib/statistics's covariance() passes generator expressions to sumprod() (#490): each is a
# generator, which _sumprod() reads into a list (a generator has no __len__)
import statistics

print(statistics.covariance([1.0, 2.0, 3.0], [1.0, 3.0, 2.0]))
print(statistics.covariance([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0], [9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0]))
