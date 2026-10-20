# examples/csvstat: the statistics of each column of 3,000 generated orders, which csv.writer writes
# to an object of the program's and csv.reader reads back as the lines of a file, as CPython prints
# them; then a file whose rows are shorter and longer than its header
import csv

import csvstat
import gencsv


class Lines:
    # what a writer writes, kept
    def __init__(self) -> None:
        self.parts: list[str] = []

    def write(self, s: str) -> int:
        self.parts.append(s)
        return 0


out = Lines()
gencsv.write(3000, out)
text = "".join(out.parts)
lines = text.splitlines(True)
print(len(out.parts), len(lines), text.count("\r\n"), lines[:3])
columns, count, longer = csvstat.collect(csv.reader(lines))
csvstat.report("orders", columns, count, longer)
csvstat.report_csv(columns)
columns, count, longer = csvstat.collect(csv.reader(["a,b,c", "1,x,", "2", "3,y,z,extra", "", "4.5,w,q\n"]))
csvstat.report("ragged", columns, count, longer)
csvstat.report_csv(columns)
# ints past 2**53, which a float does not hold: the least and largest exactly, and the mean, median
# and deviation from their distances to the least
columns, count, longer = csvstat.collect(csv.reader(["id,n", "9007199254740993,1", "9007199254740992,2",
                                                     "9223372036854775807,3", "9007199254740995,4"]))
csvstat.report("big", columns, count, longer)
columns, count, longer = csvstat.collect(csv.reader(["id", "9007199254740992", "9007199254740993", "1.5"]))
csvstat.report("mixed", columns, count, longer)
columns, count, longer = csvstat.collect(csv.reader(["id", "9007199254740992", "9007199254740993"]))
print(csvstat.statistics(columns[0]))
