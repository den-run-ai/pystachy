import sys
k = len(sys.argv)
words = ["def", "main", "x", "return", "self", "for", "in", "range", "print", "None", "if", "else"]
classes = ["k", "nf", "n", "p", "o", "mi", "s2"]
parts = []
x = 11 * k
for i in range(60000):
    x = (x * 1103515245 + 12345) % 2147483648
    w = words[(x >> 4) % len(words)]
    r = (x >> 12) % 10
    if r < 5:
        parts.append('<span class="' + classes[(x >> 8) % len(classes)] + '">' + w + "</span>")
    elif r < 7:
        parts.append("<td>" + w + "</td>")
    elif r < 8:
        parts.append('<a href="#' + w + '">' + w + "</a>")
    elif r < 9:
        parts.append("<b>" + w + "</b>")
    else:
        parts.append("<br>\n")
t = "".join(parts)
n = 0
for i in range(20):
    for nd in ["</span>", "</td>"]:
        j = t.find(nd)
        while j >= 0:
            n += j % 7
            j = t.find(nd, j + 1)
print(n)
