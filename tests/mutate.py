"""검사가 실제로 잡는지 본다. 일부러 망가뜨리고 그 검사가 실패해야 한다.

    python3 tests/mutate.py

검사를 더하면 그 검사를 깨뜨리는 항목도 여기에 더한다.
원본은 임시 폴더에 떠 두었다가 끝나면 되돌린다.
"""
import glob
import json
import os
import py_compile
import shutil
import signal
import subprocess
import sys
import tempfile

from grid import ANIM, HERE, ROOT, Frame
# 줄 수는 굽고 나서 정해지므로 파일 이름에 박아 두면 크기가 바뀔 때마다 깨진다
SAMPLE = sorted(glob.glob(os.path.join(glob.escape(ANIM), "플밍이_숨쉬기_36x*.json")))[-1]
INSTALL = os.path.join(ROOT, "plmi", "install.py")
STATUS = os.path.join(ROOT, "plmi", "statusline.py")
DOT = os.path.join(ROOT, "plmi", "dot.py")
BUBBLE = os.path.join(ROOT, "plmi", "bubble.py")
PLAY = os.path.join(ROOT, "plmi", "play.py")
SUMMARY = os.path.join(ROOT, "plmi", "summary.py")
STATE = os.path.join(ROOT, "plmi", "state.py")


def fires(mod, case):
    """그 검사가 실패하면 True. run.py 처럼 밀폐한 자리에서 돌리고, 건너뛰면 못 잡은 것으로 센다."""
    code = (f"import sys; sys.path.insert(0, {HERE!r})\n"
            "import grid; grid.seal()\n"
            f"import {mod}\n"
            f"try:\n    {mod}.{case}()\nexcept grid.Skip:\n    sys.exit(3)")
    # 바이트코드를 안 쓴다. 크기가 같은 돌연변이가 같은 초에 이어지면 앞 돌연변이의 .pyc 로 판정한다
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    code_ = subprocess.run([sys.executable, "-B", "-c", code],
                           capture_output=True, text=True, timeout=600, env=env).returncode
    return code_ not in (0, 3)


def guard(paths, mutate, mod, case, label, out):
    bak = tempfile.mkdtemp()
    for p in paths:
        shutil.copy2(p, os.path.join(bak, os.path.basename(p)))
    try:
        mutate()
        broken = []
        for p in paths:
            if p.endswith(".py"):
                try:
                    py_compile.compile(p, cfile=os.path.join(bak, "check.pyc"), doraise=True)
                except py_compile.PyCompileError:
                    broken.append(os.path.basename(p))
        # 문법이 깨진 돌연변이는 어떤 검사든 실패시켜 잡은 것처럼 보인다. 못 잡은 것으로 센다
        hit = not broken and fires(mod, case)
        print(f"  {'잡음  ' if hit else '못잡음'}  {label}" + (f"  (돌연변이가 문법 오류: {broken})" if broken else ""))
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
    """아래 여백을 없앤다. 발이 모드 표시줄과 맞닿아 보이는 상태가 된다."""
    a["frames"] = ["\n".join(f.split("\n")[:-1] + ["\u28ff" * a["cw"]])
                   for f in a["frames"]]


def cmd_line():
    """install.py 에서 상태줄 명령을 만드는 줄. 명령 모양이 바뀌어도 돌연변이가 따라간다."""
    with open(INSTALL, encoding="utf-8") as f:
        return next(l.rstrip("\n") for l in f if l.startswith('    return f"{head} sh -c'))


def swap(src, old, new):
    def go():
        with open(src, encoding="utf-8") as f:
            d = f.read()
        assert old in d, f"{src} 에서 {old!r} 를 못 찾았다"
        with open(src, "w", encoding="utf-8") as f:
            f.write(d.replace(old, new, 1))
    return go


def main():
    # kill 이나 창 닫기로 끊겨도 finally 가 돌아 망가뜨린 파일을 되돌리게 한다
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, lambda *_: sys.exit(1))
    out = []
    def drop_one(a):
        rows = a["tints"][0].split("\n")
        y, x = Frame(a, 0).blush_cells()[0]
        line = list(rows[y])
        line[x] = rows[y][x + 3] if x + 3 < len(rows[y]) else "5"
        rows[y] = "".join(line)
        a["tints"][0] = "\n".join(rows)

    def move_down(a):
        rows = a["tints"][0].split("\n")
        keep = a["tints"][0].split("\n")
        for y, x in Frame(a, 0).blush_cells():
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
          "test_runtime", "test_런타임은_굽는_쪽을_안_끌어온다", "런타임에 numpy 임포트", out)
    guard([INSTALL], swap(INSTALL, "    if now and ours is None and not a.force:", "    if False:"),
          "test_install", "test_남의_statusLine_을_안_덮는다", "덮기 방지 제거", out)
    guard([INSTALL], swap(INSTALL,
                      '{shlex.quote(RUNNER)}',
                      'plmi/statusline.py'),
          "test_install", "test_절대경로를_쓴다", "상대경로로 바꿈", out)

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
          "기본 크기를 없는 크기로 박음", out)

    guard([INSTALL], swap(INSTALL, "    root = os.path.abspath(os.path.expanduser(where or os.getcwd()))",
                          "    root = os.getcwd()"),
          "test_install", "test_붙일_워크스페이스를_지목할_수_있다",
          "지목한 폴더를 무시하고 지금 폴더에 씀", out)
    guard([INSTALL], swap(INSTALL, "        if plmi_env(entry) is not None:", "        if False:"),
          "test_install", "test_붙인_자리를_찾아_준다",
          "붙은 자리를 못 알아보게", out)

    guard([STATUS], swap(STATUS, "SIZE = os.environ.get(\"PLMI_SIZE\") or default_size()",
                         "SIZE = os.environ.get(\"PLMI_SIZE\", \"26x10\")"),
          "test_runtime", "test_기본_크기는_구워_둔_것에서_고른다",
          "런타임 기본 크기를 글자로 박음", out)
    guard([STATUS], swap(STATUS, 'str(b.get("text", "")).lstrip().startswith(INTERRUPT)', "False"),
          "test_runtime", "test_여덟_상태가_모두_기록에서_나온다",
          "놀람 트리거 제거", out)
    guard([INSTALL], swap(INSTALL, "            sweep(path)", "            pass"),
          "test_install", "test_붙였다_뗀다", "뗀 뒤 빈 껍데기를 남김", out)
    guard([INSTALL], swap(INSTALL, "    if why and not a.force:",
                          "    if False:"),
          "test_install", "test_창보다_큰_크기는_막는다", "창보다 큰 크기를 통과시킴", out)

    guard([STATUS], swap(STATUS, "        if enough(out) or size >= TAIL_MAX or size >= end:",
                         "        if True:"),
          "test_runtime", "test_큰_줄이_끝에_와도_판정할_것을_찾는다",
          "꼬리 창을 안 넓힘", out)
    guard([STATUS], swap(STATUS, '    return [{"type": "text", "text": c}] if isinstance(c, str) and c else []',
                         "    return []"),
          "test_runtime", "test_사람_말이_문자열로_와도_본다",
          "문자열 블록을 무시", out)

    guard([INSTALL], swap(INSTALL, '    if a.preview is not None:', '    if False:'),
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
    guard([BUBBLE], swap(BUBBLE, "    body = wrap(text, COLS)",
                         "    body = wrap(text if shown is None else text[:shown], COLS)"),
          "test_runtime", "test_말풍선이_떠_있는_동안_상자_크기가_그대로다",
          "보이는 글자로 상자를 잼", out)
    guard([STATUS], swap(STATUS, 'draw(said + "." * DOTS, shown=len(said) + dots)',
                         'draw(said + "." * dots)'),
          "test_runtime", "test_말풍선이_떠_있는_동안_상자_크기가_그대로다",
          "느는 점이 상자를 흔듦", out)
    guard([STATUS], swap(STATUS, "TALK = (1.0, 4.0, 3.0)", "TALK = (1.0, 4.0, 0.0)"),
          "test_runtime", "test_수다는_쉬었다가_다시_말한다",
          "수다가 쉬지 않음", out)
    guard([STATUS], swap(STATUS, "            at = max(0.0, t - since)", "            at = t"),
          "test_runtime", "test_일이_난_순간부터_말한다",
          "사건 시각 대신 벽시계", out)
    guard([STATUS], swap(STATUS, "        if rest is not None:\n            at %= stay + rest",
                         "        at %= stay + (rest or 0.0)"),
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
    guard([INSTALL], swap(INSTALL, "        if ours is None and not a.force:",
                          '        if (ours is None or RUNNER not in str(now.get("command", ""))) and not a.force:'),
          "test_install", "test_어느_사본이_붙였든_뗀다",
          "다른 사본이 붙인 것을 못 떼게", out)

    guard([INSTALL], swap(INSTALL, "    if now and ours is None and not a.force:",
                          '    if now and (ours is None or RUNNER not in str(now.get("command", ""))) and not a.force:'),
          "test_install", "test_다른_사본이_붙인_자리에_그냥_붙는다",
          "다른 사본 자리에 붙이려면 --force 가 필요하게", out)

    guard([PLAY], swap(PLAY,
                       '    hits = glob.glob(os.path.join(os.path.expanduser("~/.claude/projects"), "*", "*.jsonl"))',
                       '    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n'
                       '    hits = glob.glob(os.path.join(os.path.expanduser("~/.claude/projects"), '
                       'here.replace("/", "-"), "*.jsonl"))'),
          "test_runtime", "test_창은_어느_워크스페이스의_대화든_따라간다",
          "깔린 폴더에서 돈 대화만 찾음", out)
    guard([STATUS], swap(STATUS, '        said = " ".join(clean(text).split())[:SAID]\n', '        said = " ".join(clean(text).split())\n'),
          "test_runtime", "test_말풍선이_붙어도_줄수가_그대로다",
          "긴 문구를 안 자름", out)
    guard([STATUS], swap(STATUS, 'INTERRUPT = "[Request interrupted by user"', 'INTERRUPT = "[Request interrupted by user]"'),
          "test_runtime", "test_도구를_돌리다_끊어도_놀란다",
          "도구 도중 끊기를 못 알아봄", out)
    guard([SUMMARY], swap(SUMMARY, '    if tool in ("Agent", "Task"):', '    if tool == "Task":'),
          "test_runtime", "test_서브에이전트_도구도_문구로_바꾼다",
          "Agent 도구 이름을 모름", out)
    guard([STATE], swap(STATE, "        del args[i:i + 2]\n", ""),
          "test_runtime", "test_손으로_지정할_때_hold_값이_문구로_안_들어간다",
          "hold 값이 문구로 들어감", out)
    guard([INSTALL], swap(INSTALL, "    if a.preview is not None:\n", "    if a.preview:\n"),
          "test_install", "test_0초_미리보기와_0칸_굽기는_붙이지_않는다",
          "0초 미리 보기가 붙여 버림", out)
    guard([INSTALL], swap(INSTALL, "    if a.bake is not None:\n", "    if a.bake:\n"),
          "test_install", "test_0초_미리보기와_0칸_굽기는_붙이지_않는다",
          "0칸 굽기가 붙여 버림", out)
    guard([INSTALL], swap(INSTALL, "def save(path, data, backup=True):", "def save(path, data, backup=False):"),
          "test_install", "test_쓰기_전에_백업한다", "백업을 안 뜸", out)
    guard([INSTALL], swap(INSTALL, "        if ours is None and not a.force:", "        if False:"),
          "test_install", "test_남의_statusLine_은_안_뗀다", "남의 statusLine 도 뗌", out)
    guard([INSTALL], swap(INSTALL, "        if old and plmi_env(old) is None:", "        if False:"),
          "test_install", "test_강제로_덮었다_떼도_원래_설정의_백업은_남는다", "원래 설정 백업까지 치움", out)
    guard([INSTALL], swap(INSTALL, "            save(path, data, backup=ours is None)",
                          "            save(path, data, backup=False)"),
          "test_install", "test_남의_statusLine_을_강제로_떼면_백업을_남긴다", "남의 것을 떼며 백업 안 뜸", out)
    guard([INSTALL], swap(INSTALL, "        while os.path.exists(bak):", "        while False:"),
          "test_install", "test_같은_초에_두_번_백업해도_앞_백업을_안_덮는다", "같은 초 백업이 앞 백업을 덮음", out)
    guard([INSTALL], swap(INSTALL, '    sys.exit(f"statusline.py 를 못 찾았다: {RUNNER}")', "    raise"),
          "test_install", "test_statusline_py_가_없으면_알려_준다", "없다는 안내 대신 트레이스백", out)
    guard([INSTALL], swap(INSTALL, "        data = None\n", "        raise\n"),
          "test_install", "test_settings_json_이_깨졌으면_손대지_않고_알려_준다", "깨진 설정에서 트레이스백", out)
    guard([INSTALL], swap(INSTALL, "(1 + COLS + 4 if bubble else 0)", "0"),
          "test_install", "test_창_크기는_말풍선_폭까지_센다", "창 크기에 말풍선을 안 셈", out)
    guard([INSTALL], swap(INSTALL, "    # 굽기, 찾기, 떼기는 스프라이트가 없어도 한다\n",
                          "    if not SIZES:\n        sys.exit(NO_SPRITES)\n"),
          "test_install", "test_스프라이트가_없는_사본으로도_뗀다", "스프라이트가 없으면 못 뗌", out)
    guard([STATUS], swap(STATUS, "        for size in (SIZE, default_size()):",
                         '        for size in (SIZE, "16x8" if len(name) == 2 else "36x16"):'),
          "test_runtime", "test_굽지_않은_크기면_상태마다_같은_크기를_쓴다", "상태마다 다른 크기를 집음", out)
    guard([SUMMARY], swap(SUMMARY, "[:NAME]} 읽는 중", "} 읽는 중"),
          "test_runtime", "test_긴_이름을_잘라도_하는_일은_남는다", "긴 파일 이름이 동사를 밀어냄", out)
    guard([STATUS], swap(STATUS, '        said = " ".join(clean(text).split())[:SAID]\n', "        said = clean(text).rstrip()[:SAID]\n"),
          "test_runtime", "test_앞뒤_공백이_있어도_점이_제자리에서_는다", "공백 섞인 문구에서 점이 미리 보임", out)

    guard([INSTALL], swap(INSTALL, cmd_line(),
                          '    return f"{head} python3 {shlex.quote(RUNNER)}"'),
          "test_install", "test_떼는_순서를_안_지켜도_조용하다",
          "감싸지 않고 바로 부름", out)
    guard([INSTALL], swap(INSTALL, cmd_line(),
                          '    return f"{head} sh -c '
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
