"""검사가 실제로 잡는지 본다. 일부러 망가뜨리고 그 검사가 실패해야 한다.

    python3 tests/mutate.py

통과만 하는 검사는 없느니만 못하다. 검사를 고치거나 더할 때 여기도 같이 늘린다.
원본은 임시 폴더에 떠 두었다가 끝나면 되돌린다.
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ANIM = os.path.join(ROOT, "plmi", "sprites", "anim")
CHARS = "0123456789abcdefghijklmn"
# 줄 수는 굽고 나서 정해지므로 파일 이름에 박아 두면 크기가 바뀔 때마다 깨진다
SAMPLE = sorted(glob.glob(os.path.join(ANIM, "플밍이_숨쉬기_36x*.json")))[-1]
INSTALL = os.path.join(ROOT, "plmi", "install.py")
STATUS = os.path.join(ROOT, "plmi", "statusline.py")
DOT = os.path.join(ROOT, "plmi", "dot.py")
BUBBLE = os.path.join(ROOT, "plmi", "bubble.py")


def fires(mod, case):
    """그 검사가 실패하면 True."""
    code = f"import sys; sys.path.insert(0, {HERE!r})\nimport {mod}; {mod}.{case}()"
    return subprocess.run([sys.executable, "-c", code],
                          capture_output=True, text=True, timeout=600).returncode != 0


def guard(paths, mutate, mod, case, label, out):
    bak = tempfile.mkdtemp()
    for p in paths:
        shutil.copy2(p, os.path.join(bak, os.path.basename(p)))
    try:
        mutate()
        hit = fires(mod, case)
        print(f"  {'잡음  ' if hit else '못잡음'}  {label}")
        out.append((label, hit))
    finally:
        for p in paths:
            shutil.copy2(os.path.join(bak, os.path.basename(p)), p)
        shutil.rmtree(bak)


def sprite(fn):
    def go():
        with open(SAMPLE, encoding="utf-8") as f:
            a = json.load(f)
        fn(a)
        with open(SAMPLE, "w", encoding="utf-8") as f:
            json.dump(a, f, ensure_ascii=False)
    return go


def fill_bottom(a):
    """아래 여백을 없앤다. 모드 표시줄과 맞닿아 보이던 그 상태로 되돌린다."""
    a["frames"] = ["\n".join(f.split("\n")[:-1] + ["\u28ff" * a["cw"]])
                   for f in a["frames"]]


def cmd_line():
    """install.py 에서 상태줄 명령을 만드는 줄. 명령 모양이 바뀌어도 돌연변이가 따라간다."""
    with open(INSTALL, encoding="utf-8") as f:
        return next(l.rstrip("\n") for l in f if l.startswith('    return f"PLMI_SIZE='))


def swap(src, old, new):
    def go():
        with open(src, encoding="utf-8") as f:
            d = f.read()
        assert old in d, f"{src} 에서 {old!r} 를 못 찾았다"
        with open(src, "w", encoding="utf-8") as f:
            f.write(d.replace(old, new, 1))
    return go


def blush_cells(a, i=0):
    rows = a["tints"][i].split("\n")
    return [(y, x) for y, r in enumerate(rows) for x, c in enumerate(r)
            if c != "." and a["palette"][CHARS.index(c)][0]
            > a["palette"][CHARS.index(c)][1] + 15]


def main():
    out = []
    def drop_one(a):
        rows = a["tints"][0].split("\n")
        y, x = blush_cells(a)[0]
        line = list(rows[y])
        line[x] = rows[y][x + 3] if x + 3 < len(rows[y]) else "5"
        rows[y] = "".join(line)
        a["tints"][0] = "\n".join(rows)

    def move_down(a):
        rows = a["tints"][0].split("\n")
        keep = a["tints"][0].split("\n")
        for y, x in blush_cells(a):
            line = list(rows[y])
            line[x] = keep[y][x - 4] if x >= 4 else "5"
            rows[y] = "".join(line)
            below = list(rows[y + 1])
            below[x] = keep[y][x]
            rows[y + 1] = "".join(below)
        a["tints"][0] = "\n".join(rows)

    def flat_top(a):
        f = a["frames"][0].split("\n")
        f[0] = "⣿" * a["cw"]
        a["frames"][0] = "\n".join(f)

    def all_same(a):
        a["frames"] = [a["frames"][0]] * len(a["frames"])

    def short_row(a):
        a["frames"][0] = "\n".join(a["frames"][0].split("\n")[:-1])

    guard([SAMPLE], sprite(drop_one), "test_sprites",
          "test_볼_좌우_크기가_같다", "볼 한쪽을 한 칸 줄임", out)
    guard([SAMPLE], sprite(move_down), "test_sprites",
          "test_볼이_입_윗점이_든_칸에_있다", "볼을 한 줄 내림", out)
    guard([SAMPLE], sprite(flat_top), "test_sprites",
          "test_머리가_안_잘린다", "맨 윗줄을 평평하게", out)
    guard([SAMPLE], sprite(all_same), "test_sprites",
          "test_상태마다_서로_다른_그림이_충분하다", "전 프레임을 같게", out)
    guard([SAMPLE], sprite(short_row), "test_sprites",
          "test_파일이름의_줄수와_실제_줄수가_같다", "한 줄 없앰", out)
    guard([STATUS], swap(STATUS, "import glob", "import glob\nimport numpy"),
          "test_runtime", "test_굽는_쪽은_런타임을_안_끌어온다", "런타임에 numpy 임포트", out)
    guard([INSTALL], swap(INSTALL, "if now and not any_plmi(now) and not a.force:", "if False:"),
          "test_install", "test_남의_statusLine_을_안_덮는다", "덮기 방지 제거", out)
    guard([INSTALL], swap(INSTALL,
                      '{shlex.quote(RUNNER)}',
                      'plmi/statusline.py'),
          "test_install", "test_절대경로를_쓴다", "상대경로로 바꿈", out)

    # 기하를 Layout 밖으로 도로 풀어 쓰는 것이 이 코드가 늘 되돌아가던 자리다
    guard([DOT], swap(DOT, '    body, face = m["body"], m["face"]',
                      '    body, face = m["body"], m["face"]\n'
                      "    ox2 = (lay.W - lay.tw0) // 2 + (lay.tw0 - lay.tw) // 2"),
          "test_layout", "test_기하식은_Layout_안에만_있다",
          "가로 오프셋 식을 fit 안에 다시 씀", out)
    guard([DOT], swap(DOT, "def fit_color(m, lay, sub=5, gain=1.0):",
                      "def fit_color(m, lay, cw=26, sub=5, gain=1.0):"),
          "test_layout", "test_얼굴과_몸과_색이_같은_Layout_을_받는다",
          "fit_color 가 칸 수를 따로 받게", out)

    guard([SAMPLE], sprite(fill_bottom), "test_sprites",
          "test_아래에_빈_줄이_있다", "맨 아랫줄을 채움", out)

    guard([INSTALL], swap(INSTALL, "HERE = os.path.dirname(stable(__file__))",
                          "HERE = os.path.dirname(os.path.realpath(__file__))"),
          "test_install", "test_brew_로_깔면_버전_없는_경로를_쓴다",
          "brew 경로를 Cellar 그대로 씀", out)

    guard([INSTALL], swap(INSTALL, 'default=DEFAULT_SIZE', 'default="26x10"'),
          "test_install", "test_기본_크기가_실제로_있는_크기다",
          "기본 크기를 옛 줄 수로 박음", out)

    guard([INSTALL], swap(INSTALL, "    root = os.path.abspath(os.path.expanduser(where or os.getcwd()))",
                          "    root = os.getcwd()"),
          "test_install", "test_붙일_워크스페이스를_지목할_수_있다",
          "지목한 폴더를 무시하고 지금 폴더에 씀", out)
    guard([INSTALL], swap(INSTALL, 'return "PLMI_SIZE" in cmd and "statusline.py" in cmd',
                          "return False"),
          "test_install", "test_붙인_자리를_찾아_준다",
          "붙은 자리를 못 알아보게", out)

    guard([STATUS], swap(STATUS, "SIZE = os.environ.get(\"PLMI_SIZE\") or default_size()",
                         "SIZE = os.environ.get(\"PLMI_SIZE\", \"26x10\")"),
          "test_runtime", "test_기본_크기는_구워_둔_것에서_고른다",
          "런타임 기본 크기를 글자로 박음", out)
    guard([STATUS], swap(STATUS, '"[Request interrupted by user]" in str(b.get("text", ""))',
                         "False"),
          "test_runtime", "test_여덟_상태가_모두_기록에서_나온다",
          "놀람 트리거 제거", out)
    guard([INSTALL], swap(INSTALL, "            sweep(path)", "            pass"),
          "test_install", "test_붙였다_뗀다", "뗀 뒤 빈 껍데기를 남김", out)
    guard([INSTALL], swap(INSTALL, "    if not a.uninstall and not fits(a.size) and not a.force:",
                          "    if False:"),
          "test_install", "test_창보다_큰_크기는_막는다", "창보다 큰 크기를 통과시킴", out)

    guard([STATUS], swap(STATUS, "        if sum(len(blocks(e)) for e in out) >= NEED or size >= TAIL_MAX or size >= end:",
                         "        if True:"),
          "test_runtime", "test_큰_줄이_끝에_와도_판정할_것을_찾는다",
          "꼬리 창을 안 넓힘", out)
    guard([STATUS], swap(STATUS, '    return [{"type": "text", "text": c}] if isinstance(c, str) and c else []',
                         "    return []"),
          "test_runtime", "test_사람_말이_문자열로_와도_본다",
          "문자열 블록을 다시 무시", out)

    guard([INSTALL], swap(INSTALL, '    if a.preview:', '    if False:'),
          "test_install", "test_붙이지_않고_미리_볼_수_있다",
          "미리 보기를 끔", out)

    guard([STATUS], swap(STATUS, 'return "뾰로통", "심심해"', 'return "뾰로통", ""'),
          "test_runtime", "test_오래_쉬면_심심하다고_한다",
          "심심해 문구 제거", out)

    guard([STATUS], swap(STATUS, "    return int(at / beat) % (DOTS + 1)", "    return 0"),
          "test_runtime", "test_문구는_한꺼번에_뜨고_점이_하나씩_는다",
          "점이 안 늚", out)
    guard([STATUS], swap(STATUS, "TALK = (1.0, 4.0, 3.0)", "TALK = (0.5, 4.0, 3.0)"),
          "test_runtime", "test_쉴_때_불리는_간격으로_봐도_점이_하나씩_는다",
          "쉴 때 점을 너무 빨리 늘림", out)
    guard([STATUS], swap(STATUS, '    "승인대기": (1.0, None, None),', '    "승인대기": (0.5, None, None),'),
          "test_runtime", "test_쉴_때_불리는_간격으로_봐도_점이_하나씩_는다",
          "허락 기다릴 때 점을 너무 빨리 늘림", out)
    guard([BUBBLE], swap(BUBBLE, "    body = wrap(text, cols)",
                         "    body = wrap(text if shown is None else text[:shown], cols)"),
          "test_runtime", "test_말풍선이_떠_있는_동안_상자_크기가_그대로다",
          "보이는 글자로 상자를 잼", out)
    guard([STATUS], swap(STATUS, 'draw(said + "." * DOTS, cols=22, shown=len(said) + dots)',
                         'draw(said + "." * dots, cols=22)'),
          "test_runtime", "test_말풍선이_떠_있는_동안_상자_크기가_그대로다",
          "느는 점이 상자를 흔듦", out)
    guard([STATUS], swap(STATUS, "TALK = (1.0, 4.0, 3.0)", "TALK = (1.0, 4.0, 0.0)"),
          "test_runtime", "test_수다는_쉬었다가_다시_말한다",
          "수다가 쉬지 않음", out)
    guard([STATUS], swap(STATUS, "            at = max(0.0, t - since)", "            at = t"),
          "test_runtime", "test_일이_난_순간부터_말한다",
          "사건 시각 대신 벽시계", out)
    guard([STATUS], swap(STATUS, "        if rest is not None:\n            at %= hold + rest",
                         "        at %= hold + (rest or 0.0)"),
          "test_runtime", "test_외치는_말은_한_번만_한다",
          "외치는 말을 되풀이", out)
    guard([STATUS], swap(STATUS, '    "작업중": (0.5, None, None),', '    "작업중": (0.5, 4.0, 3.0),'),
          "test_runtime", "test_일하는_중에는_말풍선이_안_사라진다",
          "일하는 중에 쉼", out)
    guard([STATUS], swap(STATUS, "            at, rest = t, TALK[2] if rest is None else rest",
                         "            at = t"),
          "test_runtime", "test_언제_꺼낸_말인지_몰라도_보인다",
          "시각을 모르면 한 번만 할 말이 안 보임", out)
    guard([STATUS], swap(STATUS, '                    return "놀람", "앗", at',
                         '                    return "놀람", "앗", None'),
          "test_runtime", "test_말을_꺼낸_시각을_기록에서_읽는다",
          "사건 시각을 안 넘김", out)
    guard([INSTALL], swap(INSTALL, "        if not any_plmi(now) and not a.force:",
                          '        if RUNNER not in str(now.get("command", "")) and not a.force:'),
          "test_install", "test_어느_사본이_붙였든_뗀다",
          "다른 사본이 붙인 것을 못 떼게", out)

    guard([INSTALL], swap(INSTALL, "    if now and not any_plmi(now) and not a.force:",
                          '    if now and RUNNER not in str(now.get("command", "")) and not a.force:'),
          "test_install", "test_다른_사본이_붙인_자리에_그냥_붙는다",
          "다른 사본 자리에 붙이려면 --force 가 필요하게", out)

    # 넣을 문자는 코드 번호로 만든다. 글자 그대로 적으면 이 파일이 글쓰기 검사에 걸린다
    mark = "HERE = os.path.dirname(os.path.abspath(__file__))"
    guard([STATUS], swap(STATUS, mark, mark + "  # " + chr(0x1F534) + " 표시"),
          "test_writing", "test_이모지를_안_쓴다", "주석에 이모지", out)
    guard([STATUS], swap(STATUS, mark, mark + "  # 하나" + chr(0x2014) + "둘"),
          "test_writing", "test_em_dash_를_안_쓴다", "주석에 em dash", out)
    guard([STATUS], swap(STATUS, mark, mark + "  # "
                         + "".join(map(chr, (0xC804, 0xC5D0, 0xB294))) + " 달랐다"),
          "test_writing", "test_코드에_변경_이력을_안_적는다", "주석에 이력 어투", out)


    guard([INSTALL], swap(INSTALL, cmd_line(),
                          '    return f"PLMI_SIZE={size} python3 {shlex.quote(RUNNER)}"'),
          "test_install", "test_떼는_순서를_안_지켜도_조용하다",
          "감싸지 않고 바로 부름", out)
    guard([INSTALL], swap(INSTALL, cmd_line(),
                          '    return f"PLMI_SIZE={size} sh -c '
                          + "'exec python3 {RUNNER} 2>/dev/null'" + '"'),
          "test_install", "test_공백이_든_경로에서도_돈다",
          "경로를 명령 안에 그대로 넣음", out)

    missed = [label for label, hit in out if not hit]
    print(f"\n망가뜨린 {len(out)}가지 중 {len(out) - len(missed)}가지를 잡았다")
    if missed:
        print("못 잡은 것: " + ", ".join(missed))
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
