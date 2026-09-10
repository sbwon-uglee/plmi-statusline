"""구워 놓은 스프라이트가 지켜야 하는 것들.

여기 적힌 검사는 전부 한 번씩 실제로 깨졌던 것이다. 무엇이 어떻게 깨졌는지는
`docs/DECISIONS.md`.
"""
import grid


def test_모든_크기에_여덟_상태가_있다():
    for size in grid.sizes():
        for state in grid.STATES:
            a = grid.load(state, size)
            assert a["frames"], f"{size} {state} 가 비었다"
            assert len(a["frames"]) == len(a["tints"]), f"{size} {state} 그림과 색의 수가 다르다"


def test_파일이름의_줄수와_실제_줄수가_같다():
    for size in grid.sizes():
        rows = int(size.split("x")[1])
        for state in grid.STATES:
            a = grid.load(state, size)
            assert a["ch"] == rows, f"{size} {state}: ch={a['ch']}"
            for i, f in enumerate(a["frames"]):
                assert len(f.split("\n")) == rows, f"{size} {state} {i}번 줄 수"


def test_색_문자가_팔레트_안에_있다():
    for size in grid.sizes():
        for state in grid.STATES:
            a = grid.load(state, size)
            n = len(a["palette"])
            for i, t in enumerate(a["tints"]):
                for ch in t:
                    if ch in ".\n":
                        continue
                    assert grid.CHARS.index(ch) < n, f"{size} {state} {i}번 색 {ch}"


def test_머리가_안_잘린다():
    """늘어난 프레임이 격자 위로 삐져나가면 맨 윗줄이 평평하게 잘린다."""
    for size in grid.sizes():
        for state, i, fr in grid.frames(size):
            run, wide = fr.top_run()
            assert run <= wide * 0.5, f"{size} {state} {i}번 윗줄 {run}점 / 몸통 {wide}점"


def test_볼_좌우_크기가_같다():
    for size in grid.sizes():
        for state, i, fr in grid.frames(size):
            left, right = fr.split(fr.blush_cells())
            if not left or not right:
                continue
            assert len(left) == len(right), f"{size} {state} {i}번 좌 {len(left)} 우 {len(right)}"


def test_볼이_눈이나_입과_안_겹친다():
    for size in grid.sizes():
        for state, i, fr in grid.frames(size):
            face = set(fr.face_cells())
            hit = [c for c in fr.blush_cells() if c in face]
            assert not hit, f"{size} {state} {i}번 {hit}"


def test_상태마다_서로_다른_그림이_충분하다():
    """같은 그림만 돌면 멈춘 것으로 보인다."""
    for size in grid.sizes():
        for state in grid.STATES:
            a = grid.load(state, size)
            uniq = len(set(a["frames"]))
            assert uniq >= max(3, len(a["frames"]) * 0.4), \
                f"{size} {state}: {len(a['frames'])}장 중 서로 다른 것 {uniq}장"


def test_얼굴이_있다():
    """눈과 입이 파여 있어야 얼굴로 읽힌다."""
    for size in grid.sizes():
        for state, i, fr in grid.frames(size):
            assert fr.face_cells(), f"{size} {state} {i}번에 파인 칸이 없다"


def test_볼이_양쪽에_있다():
    for size in grid.sizes():
        for state, i, fr in grid.frames(size):
            left, right = fr.split(fr.blush_cells())
            assert left and right, f"{size} {state} {i}번 좌 {len(left)} 우 {len(right)}"


def test_볼이_입_윗점이_든_칸에_있다():
    """볼 줄과 입 줄을 따로 반올림하면 몸이 눌릴 때 간격이 프레임마다 튄다.

    눈 둘과 입 하나가 따로 떨어져 보이는 프레임에서만 잴 수 있다. 작은 크기에서는
    셋이 한 덩어리로 붙어 입만 떼어낼 수가 없다. 그런 프레임은 건너뛰되, 가장 큰
    크기에서는 거의 다 재져야 한다. 안 그러면 검사가 헛도는 것이다.
    """
    big = grid.sizes()[0]
    for size in grid.sizes():
        checked, skipped, bad = 0, 0, []
        for state, i, fr in grid.frames(size):
            groups = [g for g in fr.dot_groups() if len(g) >= 2]
            blush = fr.blush_cells()
            if len(groups) < 3 or not blush:      # 눈 둘과 입이 안 갈린다
                skipped += 1
                continue
            checked += 1
            mouth = max(groups, key=lambda g: sum(r for r, _ in g) / len(g))
            gap = min(r for r, _ in mouth) // 4 - min(y for y, _ in blush)
            if gap != 0:
                bad.append(f"{state}{i}({gap})")
        assert not bad, f"{size}: {bad[:6]}"
        if size == big:
            assert checked >= (checked + skipped) * 0.9, \
                f"{big}: 잰 것이 {checked}개뿐이고 {skipped}개를 건너뛰었다"

def test_아래에_빈_줄이_있다():
    """statusLine 바로 밑에 모드 표시줄이 붙는다. 발이 맨 아랫줄까지 닿으면 맞닿아 보인다.

    잘라내기는 어느 프레임에서도 안 쓰는 줄을 위아래로 걷어 낸다. 그래서 여백을 두려면
    걷어 낸 뒤에 붙여야 하는데, 그 자리를 지우면 조용히 원래대로 돌아간다.
    """
    for size in grid.sizes():
        for state in grid.STATES:
            a = grid.load(state, size)
            for i, f in enumerate(a["frames"]):
                last = f.split("\n")[-1]
                assert set(last) == {"\u2800"}, f"{size} {state} {i}번 맨 아랫줄에 점이 있다"
            for i, t in enumerate(a["tints"]):
                last = t.split("\n")[-1]
                assert set(last) == {"."}, f"{size} {state} {i}번 맨 아랫줄에 색이 있다"

def test_뾰로통은_눈을_뜨고_있다():
    """입만 시무룩하다. 눈까지 찌푸린 얼굴이 오래 띄워 둔 세션의 기본이 되면 안 된다.

    파낸 눈 자리의 넓이로 본다. 찌푸린 눈은 뜬눈보다 좁다.
    """
    for size in grid.sizes():
        rest = grid.Frame(grid.load("숨쉬기", size), 0)
        sulk = grid.Frame(grid.load("뾰로통", size), 0)
        eyes = lambda f: sum(1 for y, x in f.carved_dots()
                             if y < max(yy for yy, _ in f.carved_dots()) - 1)
        assert eyes(sulk) >= eyes(rest) * 0.7, f"{size} 눈이 너무 좁다"
