"""검사들이 함께 쓰는 것. 밀폐, 건너뛰기, 파이썬 목록, 스프라이트를 점과 칸으로 풀어 읽기."""
import atexit
import glob
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ANIM = os.path.join(ROOT, "plmi", "sprites", "anim")
CHARS = "0123456789abcdefghijklmn"
STATES = ("숨쉬기", "작업중", "생각중", "승인대기", "완료", "오류", "놀람", "뾰로통")

# 밀폐하기 전의 홈. 실제 대화 기록을 읽는 개발 저장소 전용 검사만 쓴다
REAL_HOME = os.path.expanduser("~")
SYSTEM_PY = "/usr/bin/python3"
# 상태줄 명령은 PATH 의 python3 로 돈다. 맥 기본 파이썬과 지금 파이썬을 둘 다 본다
PYTHONS = [sys.executable] + ([SYSTEM_PY] if os.path.exists(SYSTEM_PY)
                              and os.path.realpath(SYSTEM_PY) != os.path.realpath(sys.executable) else [])
# 무작위 입력 검사의 반복 배수. `python3 tests/run.py --deep` 이 올린다. 환경변수 TESTS_DEEP 로 줄일 수도 있다
DEEP = float(os.environ.get("TESTS_DEEP") or 1)


def times(n):
    """반복 수 n 에 DEEP 을 곱한다. 적어도 한 번은 돈다."""
    return max(1, round(n * DEEP))


class Skip(Exception):
    """이 자리에서는 볼 수 없는 검사. run.py 가 건너뜀으로 따로 센다."""


def slow(fn):
    """몇 초 넘게 걸리는 검사. `run.py --quick` 이 뺀다."""
    fn.slow = True
    return fn


def seal():
    """이 프로세스와 여기서 띄우는 프로세스가 이 컴퓨터의 설정을 못 보게 한다.

    HOME 을 빈 임시 폴더로 바꾸고 PLMI_ 로 시작하는 환경변수와 창 크기 변수를 지운다.
    실제 홈의 구운 크기나 셸에 켜 둔 PLMI_COLOR 가 결과를 바꾸면 검사가 거짓으로 통과한다.
    """
    cache = os.path.join(REAL_HOME, ".cache", "uv")
    if "UV_CACHE_DIR" not in os.environ and os.path.isdir(cache):
        os.environ["UV_CACHE_DIR"] = cache          # 굽기 검사가 받아 둔 numpy 를 쓰게 한다
    home = tempfile.mkdtemp(prefix="plmi-home-")
    atexit.register(shutil.rmtree, home, True)
    os.environ["HOME"] = home
    for key in list(os.environ):
        if key.startswith("PLMI_") or key in ("COLUMNS", "LINES"):
            del os.environ[key]
    return home

# 브라유 한 칸의 점 여덟 자리. 왼쪽 위부터 세로로 1 2 3 7, 오른쪽이 4 5 6 8 이다.
BITS = ((0, 0, 0x01), (1, 0, 0x02), (2, 0, 0x04), (3, 0, 0x40),
        (0, 1, 0x08), (1, 1, 0x10), (2, 1, 0x20), (3, 1, 0x80))


def sizes():
    """구워져 있는 크기를 큰 것부터. ANIM 을 바꿔 끼우면 그 폴더를 본다."""
    out = {os.path.basename(f).rsplit("_", 1)[1][:-5]
           for f in glob.glob(os.path.join(glob.escape(ANIM), "*.json"))}
    return sorted(out, key=lambda s: -int(s.split("x")[0]))


def load(state, size):
    with open(os.path.join(ANIM, f"플밍이_{state}_{size}.json"), encoding="utf-8") as f:
        return json.load(f)


def frames(size):
    """(상태, 번호, Frame) 을 차례로 낸다."""
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
        """파인 점을 붙어 있는 것끼리 묶는다. 대각선도 이어진 것으로 본다."""
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

