"""점 격자로 찍은 그림을 브라유 문자로 묶는다.

브라유 한 칸은 가로 2점 세로 4점이다. 원화를 축소해서 만든 그림은 플밍이 크기에서
눈이 1~2점으로 뭉개지므로, 점을 직접 놓아 어디에 몇 점을 줄지 정한다.

    art = ["..##..", ".####.", ...]   '#' 이 켜진 점
    print(braille(art))
"""
DOTS = [(0, 0x01), (1, 0x08), (0, 0x02), (1, 0x10),
        (0, 0x04), (1, 0x20), (0, 0x40), (1, 0x80)]   # (열, 비트) 를 행 순서로


def braille(art, on="#"):
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
                    if y < h and x < w and grid[y][x] == on:
                        col, bit = DOTS[dy * 2 + dx]
                        bits |= bit
            line += chr(0x2800 + bits)
        out.append(line)
    return "\n".join(out)


if __name__ == "__main__":
    import sys
    print(braille([l.rstrip("\n") for l in open(sys.argv[1], encoding="utf-8")]))


def halfblock(art, on="#"):
    """한 칸에 위아래 두 픽셀을 담는다. 브라유보다 성기지만 덩어리가 꽉 차 보인다."""
    h = len(art)
    w = max(len(r) for r in art)
    g = [r.ljust(w) for r in art]
    out = []
    for y0 in range(0, h, 2):
        line = ""
        for x in range(w):
            top = y0 < h and g[y0][x] == on
            bot = y0 + 1 < h and g[y0 + 1][x] == on
            line += "█" if top and bot else "▀" if top else "▄" if bot else " "
        out.append(line)
    return "\n".join(out)
