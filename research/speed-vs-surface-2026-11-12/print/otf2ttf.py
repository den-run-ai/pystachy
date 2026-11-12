"""Convert CFF-flavoured OpenType fonts to TrueType outlines (so Chromium embeds them as TrueType in PDFs).

usage: python otf2ttf.py OUTDIR FONT.otf...
"""
import sys
from pathlib import Path
from fontTools.ttLib import TTFont, newTable
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen

out = Path(sys.argv[1])
for src in sys.argv[2:]:
    font = TTFont(src)
    glyph_order = font.getGlyphOrder()
    gs = font.getGlyphSet()
    glyf = newTable("glyf")
    glyf.glyphOrder = glyph_order
    glyf.glyphs = {}
    for name in glyph_order:
        pen = TTGlyphPen(gs)
        gs[name].draw(Cu2QuPen(pen, max_err=1.0, reverse_direction=True))
        glyf.glyphs[name] = pen.glyph()
    font["glyf"] = glyf
    font["loca"] = newTable("loca")
    maxp = font["maxp"]
    maxp.tableVersion = 0x00010000
    for attr, val in (("maxZones", 1), ("maxTwilightPoints", 0), ("maxStorage", 0), ("maxFunctionDefs", 0),
                      ("maxInstructionDefs", 0), ("maxStackElements", 0), ("maxSizeOfInstructions", 0),
                      ("maxComponentElements", 0), ("maxPoints", 0), ("maxContours", 0),
                      ("maxCompositePoints", 0), ("maxCompositeContours", 0), ("maxComponentDepth", 0)):
        setattr(maxp, attr, val)
    font["head"].indexToLocFormat = 0
    font["head"].glyphDataFormat = 0
    for t in ("CFF ", "VORG"):
        if t in font:
            del font[t]
    font["post"].formatType = 3.0
    font.sfntVersion = "\x00\x01\x00\x00"
    dst = out / (Path(src).stem + ".ttf")
    font.save(dst)
    print("wrote", dst)
