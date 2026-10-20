# CPython 3.13.16 Lib/test/test_keyword.py, commit
# cbc944f4bc59639a444dd971c737788ba2283a91, SHA-256
# 9af1d7e94d0027baca8b67db0013cc94bd81c5df01d28a76dc3198537a16e8df.
# Nine complete Test_iskeyword methods: true/uppercase/None, both list-rebinding
# cases, async/await, soft keywords, and both sorted-list checks.
# unittest cleanup is written explicitly. The two exec-based methods are
# excluded because dynamic execution is outside Pystachy's subset.
# PSF License Version 2; see THIRD_PARTY_NOTICES.
import keyword

assert keyword.iskeyword('True')
assert not keyword.iskeyword('TRUE')
assert not keyword.iskeyword(None)
oldlist = keyword.kwlist
keyword.kwlist = ['its', 'all', 'eggs', 'beans', 'and', 'a', 'slice']
assert not keyword.iskeyword('eggs')
keyword.kwlist = oldlist
oldsoftlist = keyword.softkwlist
keyword.softkwlist = ['foo', 'bar', 'spam', 'egs', 'case']
assert not keyword.issoftkeyword('spam')
keyword.softkwlist = oldsoftlist
assert 'async' in keyword.kwlist
assert 'await' in keyword.kwlist
for key in ['type', 'match', 'case', '_']:
    assert key in keyword.softkwlist
assert sorted(keyword.kwlist) == keyword.kwlist
assert sorted(keyword.softkwlist) == keyword.softkwlist
print('Test_iskeyword: nine supported upstream methods passed')

# Additional predicates and mutation checks preserve frozen snapshots.
for key in keyword.kwlist:
    assert keyword.iskeyword(key)
    assert not keyword.issoftkeyword(key)
for key in keyword.softkwlist:
    assert keyword.issoftkeyword(key)
    assert not keyword.iskeyword(key)
keyword.kwlist.append('added_after_import')
keyword.softkwlist.append('soft_added_after_import')
assert not keyword.iskeyword('added_after_import')
assert not keyword.issoftkeyword('soft_added_after_import')
assert keyword.iskeyword('class')
assert keyword.issoftkeyword('match')
assert not keyword.issoftkeyword(None)
for key in ['', 'Class', 'Match', 'é', '中', '😀']:
    assert not keyword.iskeyword(key)
    assert not keyword.issoftkeyword(key)
print('Keyword membership, Unicode and snapshot mutation passed')
