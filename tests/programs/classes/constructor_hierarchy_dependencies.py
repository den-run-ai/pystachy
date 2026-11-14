from mods.constructor_hierarchy import Total, SourceHolder


# SourceHolder's annotations name a base that is still a class template on the
# first attempt. Check the base's layout before deciding the child's layout.
value = SourceHolder(Total([3, 4]))
print(value.score(), value.source.score(), isinstance(value, Total))
