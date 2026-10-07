"""Stdlib PNG reader for RGBA alpha bounds (8-bit, colour type 6 or 2). Used to place ESPN cutouts."""
import struct, zlib
from pathlib import Path


def read(path):
    data = Path(path).read_bytes()
    pos, idat = 8, b''
    w = h = ct = None
    while pos < len(data):
        n, kind = struct.unpack('>I4s', data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + n]
        if kind == b'IHDR':
            w, h, depth, ct = struct.unpack('>IIBB', body[:10])
            assert depth == 8, depth
        elif kind == b'IDAT':
            idat += body
        pos += 12 + n
    bpp = {6: 4, 2: 3, 4: 2, 0: 1}[ct]
    raw = zlib.decompress(idat)
    stride = w * bpp
    rows, prev = [], bytearray(stride)
    i = 0
    for _ in range(h):
        f = raw[i]; i += 1
        line = bytearray(raw[i:i + stride]); i += stride
        for x in range(stride):
            a = line[x - bpp] if x >= bpp else 0
            b = prev[x]
            c = prev[x - bpp] if x >= bpp else 0
            if f == 1: line[x] = (line[x] + a) & 255
            elif f == 2: line[x] = (line[x] + b) & 255
            elif f == 3: line[x] = (line[x] + ((a + b) >> 1)) & 255
            elif f == 4:
                p = a + b - c; pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[x] = (line[x] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(bytes(line)); prev = line
    return w, h, bpp, rows


def profile(path, thresh=40):
    """Per-row (min_x, max_x) of opaque pixels, plus the overall bbox."""
    w, h, bpp, rows = read(path)
    out = []
    for y, line in enumerate(rows):
        xs = [x for x in range(w) if (line[x * bpp + bpp - 1] if bpp in (4, 2) else 255) > thresh]
        out.append((xs[0], xs[-1]) if xs else None)
    ys = [y for y, r in enumerate(out) if r]
    return w, h, out, (min(r[0] for r in out if r), ys[0], max(r[1] for r in out if r), ys[-1])


if __name__ == '__main__':
    import sys
    for p in sys.argv[1:]:
        w, h, prof, bbox = profile(p)
        print(Path(p).name, w, h, 'bbox', bbox)
        for y in range(0, h, 40):
            print('  y', y, prof[y])
