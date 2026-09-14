"""격자 기하를 Layout 한 곳에서만 정하는지 본다.

`fit`, `face_art`, `fit_color` 가 기하를 따로 세우면 한 곳만 고쳤을 때 볼과 색이 얼굴과 어긋난다.

numpy 없이 돌아야 하므로 `dot` 을 임포트하지 않고 소스를 읽는다.
"""
import ast
import os
import re

import grid

with open(os.path.join(grid.ROOT, "plmi", "dot.py"), encoding="utf-8") as f:
    SRC = f.read()

# 변수 이름이 바뀌어도 걸리도록 식의 모양으로 찾는다
GEOMETRY = (
    ("채움 배율", r"2 \* pad\) /"),
    ("기준 크기", r"round\(\w*\.?w \* \w*\.?scale\)"),
    ("가로 오프셋", r"// 2 \+ \(\w*\.?tw0 - \w*\.?tw\) // 2"),
    ("세로 오프셋", r"// 2 \+ \(\w*\.?th0 - \w*\.?th\)"),
    ("원화 되돌리기", r"\* \w*\.?h / \w*\.?th"),
)
SHARE = ("fit", "face_art", "fit_color")
# 이 인자를 따로 받으면 부르는 쪽마다 기하가 어긋날 수 있다
BANNED = ("cw", "ch", "scale", "squeeze", "sx", "sy", "dx", "dy", "pad")


def _layout_span():
    """Layout 클래스 본문이 차지하는 글자 범위."""
    start = SRC.index("class Layout:")
    nxt = re.search(r"\n(?:def|class) ", SRC[start:])
    return start, start + (nxt.start() if nxt else len(SRC) - start)


def _args(name):
    for node in ast.parse(SRC).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return [a.arg for a in node.args.args]
    raise AssertionError(f"{name} 를 못 찾았다")


def test_기하식은_Layout_안에만_있다():
    lo, hi = _layout_span()
    for name, pat in GEOMETRY:
        outside = [SRC[:m.start()].count("\n") + 1
                   for m in re.finditer(pat, SRC) if not lo <= m.start() < hi]
        assert not outside, f"{name} 식이 Layout 밖 {outside} 줄에 있다"


def test_얼굴과_몸과_색이_같은_Layout_을_받는다():
    for name in SHARE:
        args = _args(name)
        assert len(args) > 1 and args[1] == "lay", f"{name} 의 둘째 인자가 {args[1:2]}"
        left = [a for a in BANNED if a in args]
        assert not left, f"{name} 이 {left} 를 아직 따로 받는다"


def test_Layout_이_기하를_다_들고_있다():
    lo, hi = _layout_span()
    body = SRC[lo:hi]
    for want in ("tw0", "th0", "tw", "th", "ox", "oy", "scale"):
        assert re.search(rf"self\.{want}\s*=", body), f"Layout 에 {want} 가 없다"
    for name, pat in GEOMETRY:
        assert re.search(pat, body), f"{name} 식이 Layout 안에 없다"
