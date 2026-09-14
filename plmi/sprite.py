"""점 격자로 찍은 그림을 브라유 문자로 묶는다. 브라유 한 칸은 가로 2점 세로 4점이다.

    art = ["..##..", ".####.", ...]   '#' 이 켜진 점
    print(braille(art))
"""
BITS = (0x01, 0x08, 0x02, 0x10, 0x04, 0x20, 0x40, 0x80)   # 위 줄부터 왼쪽, 오른쪽 순


def braille(art):
    h = len(art)
    w = max(len(r) for r in art)
    grid = [r.ljust(w) for r in art]
    out = []
    for y0 in range(0, h, 4):
        line = ""
        for x0 in range(0, w, 2):
            bits = 0
            for dy in range(4):
                for dx in range(2):
                    y, x = y0 + dy, x0 + dx
                    if y < h and x < w and grid[y][x] == "#":
                        bits |= BITS[dy * 2 + dx]
            line += chr(0x2800 + bits)
        out.append(line)
    return "\n".join(out)
