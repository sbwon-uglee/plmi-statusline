"""말풍선을 그리는 규칙을 사례로 못 박는다.

무작위 입력 검사는 bubble.cells 로 폭을 재서, 칸 수 계산 자체가 틀리면 그리는 쪽과 재는 쪽이 같이
틀려 못 잡는다. 글자 칸 수는 여기서 터미널 기준 값으로 따로 적는다.
"""
import os
import sys

import grid

sys.path.insert(0, os.path.join(grid.ROOT, "plmi"))
import bubble  # noqa: E402

# (글자, 터미널이 쓰는 칸 수)
WIDTHS = [
    ("a", 1), ("가", 2), (chr(0xFF21), 2),            # 전각 A
    (chr(0x1F600), 2),                                 # 이모지
    ("e" + chr(0x301), 1),                             # 결합 부호는 앞 글자에 얹힌다
    ("x" + chr(0x20DD), 1),                            # 감싸는 부호
    ("ก" + chr(0xE31), 1),                             # 결합 클래스가 0 인 결합 부호
    ("⠀", 1),                                     # 브라유 빈칸
]


def test_글자마다_터미널이_쓰는_칸_수():
    wrong = [(t, bubble.cells(t), w) for t, w in WIDTHS if bubble.cells(t) != w]
    assert not wrong, wrong


def test_줄_폭에_꼭_맞는_낱말은_자르지_않는다():
    cols = bubble.COLS
    assert bubble.pieces("a" * cols, cols) == ["a" * cols]
    assert bubble.pieces("a" * (cols + 1), cols) == ["a" * cols, "a"]
    assert bubble.pieces("가" * (cols // 2) + "나", cols) == ["가" * (cols // 2), "나"]
    fit = "a" * 10 + " " + "b" * (cols - 11)
    assert bubble.wrap(fit, cols) == [fit], bubble.wrap(fit, cols)
    assert bubble.wrap(fit + "b", cols) == ["a" * 10, "b" * (cols - 10)]


def test_꼬리는_둘째_줄에_단다():
    one = bubble.draw("짧은 말")
    assert one[1].startswith("◀"), one
    three = bubble.draw(" ".join(["가나다라마바"] * 6))
    assert len(three) >= 5, three
    marks = [i for i, row in enumerate(three) if row.startswith("◀")]
    assert marks == [2], three


def test_앞에_공백이_있어도_보이는_글자는_앞에서부터_센다():
    box = bubble.draw(" 앞뒤", shown=1)
    assert "앞" in box[1] and "뒤" not in box[1], box


def test_말풍선이_그림보다_길면_그림_아래를_채운다():
    art = "⣿⣿\n⣿⣿"
    box = bubble.draw(" ".join(["가나다라마바"] * 6))
    lines = bubble.beside(art, box).split("\n")
    assert len(lines) == len(box) + 1, lines
    assert all(l.startswith(("⣿⣿", "⠀⠀")) for l in lines), lines
