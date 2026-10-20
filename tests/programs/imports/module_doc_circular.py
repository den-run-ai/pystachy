# A partially initialized module already has its docstring or None, even when a later
# direct assignment gives __doc__ its eventual type. Both import forms observe that value.
from mods import doc_cycle_none, doc_cycle_none_reader
from mods import doc_cycle_text, doc_cycle_text_reader
from mods import doc_cycle_int, doc_cycle_int_reader
from mods import doc_cycle_ann, doc_cycle_ann_reader

print(doc_cycle_none_reader.initial, doc_cycle_none_reader.initial_from, doc_cycle_none.__doc__)
print(doc_cycle_text_reader.initial, doc_cycle_text_reader.initial_from, doc_cycle_text.__doc__)
print(doc_cycle_int_reader.initial, doc_cycle_int.__doc__)
print(doc_cycle_ann_reader.initial, doc_cycle_ann.__doc__)

import mods.doc_nocycle_type
print(mods.doc_nocycle_type.__doc__)

from mods import doc_cycle_annotation, doc_cycle_annotation_reader
print(doc_cycle_annotation_reader.initial, doc_cycle_annotation.__doc__)
