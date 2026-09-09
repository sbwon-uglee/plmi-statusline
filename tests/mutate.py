"""검사가 실제로 잡는지 본다. 일부러 망가뜨리고 그 검사가 실패해야 한다.

    python3 tests/mutate.py

통과만 하는 검사는 없느니만 못하다. 검사를 고치거나 더할 때 여기도 같이 늘린다.
원본은 임시 폴더에 떠 두었다가 끝나면 되돌린다.
"""
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
SAMPLE = os.path.join(ANIM, "플밍이_숨쉬기_36x15.json")
INSTALL = os.path.join(ROOT, "plmi", "install.py")
STATUS = os.path.join(ROOT, "plmi", "statusline.py")
DOT = os.path.join(ROOT, "plmi", "dot.py")


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
    guard([INSTALL], swap(INSTALL, "if now and not mine(now) and not a.force:", "if False:"),
          "test_install", "test_남의_statusLine_을_안_덮는다", "덮기 방지 제거", out)
    guard([INSTALL], swap(INSTALL, 'return f"PLMI_SIZE={size} python3 {RUNNER}"',
                          'return f"PLMI_SIZE={size} python3 plmi/statusline.py"'),
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

    missed = [label for label, hit in out if not hit]
    print(f"\n망가뜨린 {len(out)}가지 중 {len(out) - len(missed)}가지를 잡았다")
    if missed:
        print("못 잡은 것: " + ", ".join(missed))
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
