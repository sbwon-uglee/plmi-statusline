"""스프라이트를 점과 칸으로 풀어 읽는다. 검사들이 함께 쓴다."""
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ANIM = os.path.join(ROOT, "plmi", "sprites", "anim")
CHARS = "0123456789abcdefghijklmn"
STATES = ("숨쉬기", "작업중", "생각중", "승인대기", "완료", "오류", "놀람", "뾰로통")

# 브라유 한 칸의 점 여덟 자리. 왼쪽 위부터 세로로 1 2 3 7, 오른쪽이 4 5 6 8 이다.
BITS = ((0, 0, 0x01), (1, 0, 0x02), (2, 0, 0x04), (3, 0, 0x40),
        (0, 1, 0x08), (1, 1, 0x10), (2, 1, 0x20), (3, 1, 0x80))


def sizes():
    """구워져 있는 크기를 큰 것부터."""
    out = {os.path.basename(f).rsplit("_", 1)[1][:-5]
           for f in glob.glob(os.path.join(ANIM, "*.json"))}
    return sorted(out, key=lambda s: -int(s.split("x")[0]))


def load(state, size):
    with open(os.path.join(ANIM, f"플밍이_{state}_{size}.json"), encoding="utf-8") as f:
        return json.load(f)


def frames(size):
    """(상태, 번호, 스프라이트) 를 차례로 낸다."""
    for state in STATES:
        a = load(state, size)
        for i in range(len(a["frames"])):
            yield state, i, Frame(a, i)


class Frame:
    """한 장을 점 격자와 칸 격자로 함께 본다."""

    def __init__(self, anim, i):
        self.cw, self.ch = anim["cw"], anim["ch"]
        self.rows = anim["frames"][i].split("\n")
        self.tint = anim["tints"][i].split("\n")
        self.palette = anim["palette"]
        self.dots = [[False] * (self.cw * 2) for _ in range(self.ch * 4)]
        for y, line in enumerate(self.rows):
            for x, ch in enumerate(line):
                v = ord(ch) - 0x2800
                for dy, dx, bit in BITS:
                    if v & bit:
                        self.dots[y * 4 + dy][x * 2 + dx] = True

    def color(self, y, x):
        """그 칸의 색. 몸 바깥이면 None."""
        key = self.tint[y][x]
        return None if key == "." else tuple(self.palette[CHARS.index(key)])

    def inside(self, y, x):
        return self.tint[y][x] != "."

    def carved(self, y, x):
        """그 칸에서 안 찍힌 점의 수. 0 이면 꽉 찬 칸이다."""
        return 8 - bin(ord(self.rows[y][x]) - 0x2800).count("1")

    def body_dots(self):
        return [(y, x) for y in range(self.ch * 4) for x in range(self.cw * 2)
                if self.dots[y][x]]

    def core(self, y, x):
        """여덟 이웃이 모두 몸 안인 칸. 실루엣 가장자리를 빼고 보려는 것이다."""
        if not (0 < y < self.ch - 1 and 0 < x < self.cw - 1):
            return False
        return all(self.inside(y + dy, x + dx)
                   for dy in (-1, 0, 1) for dx in (-1, 0, 1))

    def face_cells(self):
        """눈과 입이 걸친 칸. 몸 안쪽에서 점이 파인 칸이다."""
        return [(y, x) for y in range(self.ch) for x in range(self.cw)
                if self.core(y, x) and 0 < self.carved(y, x) < 8]

    def blush_cells(self):
        """볼 칸. 붉은 기가 도는 칸을 고른다."""
        out = []
        for y in range(self.ch):
            for x in range(self.cw):
                c = self.color(y, x)
                if c and c[0] > c[1] + 15:
                    out.append((y, x))
        return out

    def split(self, cells):
        """칸 목록을 좌우로 가른다. 가운데는 그 목록의 폭에서 잡는다."""
        if not cells:
            return [], []
        mid = (min(x for _, x in cells) + max(x for _, x in cells)) / 2
        return ([c for c in cells if c[1] < mid],
                [c for c in cells if c[1] >= mid])

    def top_run(self):
        """몸의 맨 윗줄에 찍힌 점 수와 몸통 폭. 머리가 잘렸는지 보는 데 쓴다."""
        pts = self.body_dots()
        top = min(y for y, _ in pts)
        wide = max(x for _, x in pts) - min(x for _, x in pts) + 1
        return sum(1 for y, _ in pts if y == top), wide

    def carved_dots(self):
        """몸 안쪽에서 안 찍힌 점. 눈과 입을 이룬다."""
        out = []
        for y in range(self.ch):
            for x in range(self.cw):
                if not self.core(y, x) or self.carved(y, x) == 0:
                    continue
                for dy, dx, bit in BITS:
                    r, c = y * 4 + dy, x * 2 + dx
                    if not self.dots[r][c]:
                        out.append((r, c))
        return out

    def dot_groups(self):
        """붙어 있는 점끼리 묶는다. 대각선도 이어진 것으로 본다."""
        left = set(self.carved_dots())
        groups = []
        while left:
            seed = left.pop()
            group, stack = [seed], [seed]
            while stack:
                r, c = stack.pop()
                for dr in (-1, 0, 1):
                    for dc in (-1, 0, 1):
                        n = (r + dr, c + dc)
                        if n in left:
                            left.discard(n)
                            group.append(n)
                            stack.append(n)
            groups.append(group)
        return groups

    def mouth_dots(self):
        """가장 아래에 있는 덩어리가 입이다."""
        groups = [g for g in self.dot_groups() if len(g) >= 2]
        if not groups:
            return []
        return max(groups, key=lambda g: sum(r for r, _ in g) / len(g))

