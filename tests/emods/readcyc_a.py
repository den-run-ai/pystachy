# readcyc_a imports readcyc_b before its alias A = shapes.Box, and readcyc_b's code reads
# readcyc_a.A then (tests/errors/imports/import_attr_class_alias_readcycle.py)
import mods.attralias_shapes as shapes
import emods.readcyc_b

A = shapes.Box
