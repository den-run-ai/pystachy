# examples/topk: the words and pairs of words of a generated text, counted, then picked by heapq's
# nlargest() and nsmallest() and by sorting, as CPython counts and picks them
import gentext
import topk

lines = [gentext.sentence() for _ in range(300)]
print(lines[0])
words: dict[str, int] = {}
pairs: dict[tuple[str, str], int] = {}
print(topk.count(lines, words, pairs), len(words), len(pairs))
top_words, top_pairs, longest, rarest = topk.pick(10, words, pairs, False)
print(top_words)
print(top_pairs)
print(longest)
print(rarest)
print(topk.pick(10, words, pairs, True) == (top_words, top_pairs, longest, rarest))
for n in [-1, 0, 1, 2, 3, 100, 5000]:
    p = topk.pick(n, words, pairs, False)
    print(n, p == topk.pick(n, words, pairs, True), len(p[0]), len(p[1]), len(p[2]), len(p[3]), p[1][:2], p[3][-1:])
print(topk.count(["The cat, the hat.", "", "(the) THE cat -- 'cat'"], words, pairs), words["the"], words["cat"])
print(pairs["the", "cat"], pairs.get(("cat", "the"), 0), "--" in words, gentext.word(0), gentext.word(48), gentext.word(64))
