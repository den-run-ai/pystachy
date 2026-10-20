# lib/statistics's correlation() of floats: Pearson's coefficient, and Spearman's for
# method='ranked', whose ranks _rank() makes with itertools' count() and groupby() (ties share
# their average rank); its errors for too few points, inputs of different lengths, an unknown
# method and a constant input.
import statistics

x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
y = [9.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 2.0, 1.0]
print(statistics.correlation(x, x), statistics.correlation(x, y))
print(statistics.correlation([1.0, 2.0, 3.0], [1.0, 3.0, 2.0]))
print(statistics.correlation([1.0, 2.0, 3.0, 4.0, 5.0], [5.0, 4.0, 4.0, 1.0, 0.5]))
print(statistics.correlation([1.0, 2.0, 3.0, 4.0], [2.0, 4.0, 5.0, 9.0], method='ranked'))
print(statistics.correlation([1.0, 2.0, 3.0, 4.0, 5.0], [5.0, 4.0, 4.0, 1.0, 0.5], method='ranked'))
print(statistics.correlation([3.5, 1.0, 3.5, 2.0, 7.25, 0.0], [10.0, 2.0, 7.0, 7.0, 1.0, -3.0], method='ranked'))
print(statistics.correlation([0.5 * i * i for i in range(20)], [float(i) for i in range(20)], method='ranked'))
for xs, ys, method in [([1.0], [2.0], 'linear'), ([1.0, 2.0], [2.0], 'linear'), ([1.0, 2.0], [2.0, 3.0], 'x'),
                       ([1.0, 1.0], [2.0, 3.0], 'linear'), ([1.0, 1.0, 1.0], [2.0, 3.0, 1.0], 'ranked')]:
    try:
        print(statistics.correlation(xs, ys, method=method))
    except statistics.StatisticsError as e:
        print("StatisticsError:", e)
    except ValueError as e:
        print("ValueError:", e)
