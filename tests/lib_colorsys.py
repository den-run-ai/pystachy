# CPython's own Lib/colorsys.py (lib/colorsys.py, unmodified), with float and int arguments
import colorsys
from colorsys import rgb_to_hsv, hsv_to_rgb

for r, g, b in [(0.2, 0.4, 0.4), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (0.5, 0.5, 0.5), (0.0, 0.0, 0.0), (0.9, 0.1, 0.7), (1.0, 1.0, 1.0)]:
    h, s, v = rgb_to_hsv(r, g, b)
    hl = colorsys.rgb_to_hls(r, g, b)
    y = colorsys.rgb_to_yiq(r, g, b)
    print((r, g, b), (h, s, v), hl, y)
    print(hsv_to_rgb(h, s, v), colorsys.hls_to_rgb(hl[0], hl[1], hl[2]), colorsys.yiq_to_rgb(y[0], y[1], y[2]))
for k in range(7):
    print(hsv_to_rgb(k / 6.0, 0.5, 0.75), colorsys.hls_to_rgb(k / 6.0, 0.25, 1.0))
print(rgb_to_hsv(255, 0, 0), colorsys.rgb_to_hls(10, 20, 30), colorsys.rgb_to_yiq(1, 1, 1), colorsys.yiq_to_rgb(2.0, 0.0, -1.0))
print(colorsys.ONE_THIRD, colorsys.TWO_THIRD, colorsys.__all__)
