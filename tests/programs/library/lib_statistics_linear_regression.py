# lib/statistics's linear_regression() keeps its centered inputs in variables of their own (a
# variable has one type): int, float and mixed inputs, proportional or not, and its errors. The
# values come from stdin, so that no optimizer folds the arithmetic (#656)
import statistics
import sys

lines = sys.stdin.read().split("\n")
xi = [int(v) for v in lines[0].split()]
yi = [int(v) for v in lines[1].split()]
xf = [float(v) for v in lines[2].split()]
yf = [float(v) for v in lines[3].split()]

print(statistics.linear_regression(xi, yi))
print(statistics.linear_regression(xi, yi, proportional=True))
print(statistics.linear_regression(xf, yf))
print(statistics.linear_regression(xf, yf, proportional=True))
print(statistics.linear_regression(xi, yf))
slope, intercept = statistics.linear_regression(xf, yi, proportional=True)
print(slope, intercept)
result = statistics.linear_regression(yf, xf)
print(result.slope, result.intercept)

for xs, ys, proportional in (([1.0, 1.0, 1.0], [1.0, 2.0, 3.0], False),
                             ([0.0, 0.0], [1.0, 2.0], True),
                             ([1.0], [2.0], False),
                             ([1.0, 2.0], [1.0, 2.0, 3.0], True)):
    try:
        print(statistics.linear_regression(xs, ys, proportional=proportional))
    except statistics.StatisticsError as e:
        print("StatisticsError:", e)
