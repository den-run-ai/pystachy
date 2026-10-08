# mandelbrot set as ASCII art: tight float loops
def mandel(w: int, h: int, iters: int) -> list[str]:
    rows: list[str] = []
    for y in range(h):
        row: list[str] = []
        ci = (y * 2.0) / h - 1.0
        for x in range(w):
            cr = (x * 3.0) / w - 2.0
            zr = 0.0
            zi = 0.0
            k = 0
            while k < iters and zr * zr + zi * zi < 4.0:
                t = zr * zr - zi * zi + cr
                zi = 2.0 * zr * zi + ci
                zr = t
                k += 1
            row.append(" .:-=+*#%@"[k % 10] if k < iters else "@")
        rows.append("".join(row))
    return rows


img = mandel(240, 120, 2000)
print(img[60])
print(sum([r.count("@") for r in img]))
