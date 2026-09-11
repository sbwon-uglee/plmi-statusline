"""저장소 글쓰기 규칙. 사람이 키보드로 치는 문자만 쓰고, 코드에는 무엇인지를 적는다.

이 저장소 파일은 Bash 나 스크립트로 쓰는 일이 많아 편집기 쪽 검사가 못 본다.
그래서 검사로 묶어 CI 가 막게 한다.

금지 문자와 문구는 코드 번호로 조립한다. 글자 그대로 적으면 이 파일이 걸린다.
"""
import os
import re
import subprocess

import grid

def _chars(*codes):
    return "".join(chr(c) for c in codes)


# 코드 번호로 조립한다. 이스케이프로 적어도 전달 과정에서 실제 문자로 풀려 들어간 적이 있다
EMOJI = re.compile("[" + _chars(0x1F000) + "-" + _chars(0x1FAFF)
                   + _chars(0x2600) + "-" + _chars(0x27BF)
                   + _chars(0x2B00) + "-" + _chars(0x2BFF) + "]")
DASH = re.compile(_chars(0x2014))
# 앞선 판과 견줄 때만 뜻이 있는 말 네 가지. 코드에는 지금 무엇인지를 적고 사연은 기록 파일에 둔다
HISTORY = re.compile("|".join(_chars(*w) for w in (
    (0xC804, 0xC5D0, 0xB294),
    (0xC774, 0xC804, 0xC5D0, 0xB294),
    (0xAE30, 0xC874, 0xC5D0, 0xB294),
    (0xC6D0, 0xB798, 0xB294),
)))
VERSIONED = re.compile(r"\b\w+_(v\d+|old|new|tmp|temp|final|legacy)\b")

TEXT = (".py", ".md", ".sh", ".rb", ".yml", ".yaml", ".txt", ".command")
CODE = (".py", ".sh", ".rb", ".yml", ".yaml")
# 있었던 일을 적으려고 두는 파일. 여기서는 이력 어투가 본문이다
RECORDS = ("CHANGELOG.md", "docs/DECISIONS.md")


def tracked():
    try:
        out = subprocess.run(["git", "ls-files"], cwd=grid.ROOT,
                             capture_output=True, text=True, timeout=30)
        names = out.stdout.split()
    except (OSError, subprocess.SubprocessError):
        names = []
    if not names:
        names = [os.path.relpath(os.path.join(b, f), grid.ROOT)
                 for b, _, fs in os.walk(grid.ROOT) if ".git" not in b for f in fs]
    return [n for n in names
            if n.endswith(TEXT) and not n.startswith(("plmi/sprites/", "assets/"))]


def lines(name):
    with open(os.path.join(grid.ROOT, name), encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            yield i, line


def test_이모지를_안_쓴다():
    hits = [f"{n}:{i}" for n in tracked() for i, l in lines(n) if EMOJI.search(l)]
    assert not hits, "이모지: " + ", ".join(hits[:10])


def test_em_dash_를_안_쓴다():
    hits = [f"{n}:{i}" for n in tracked() for i, l in lines(n) if DASH.search(l)]
    assert not hits, "em dash: " + ", ".join(hits[:10])


def test_코드에_변경_이력을_안_적는다():
    hits = [f"{n}:{i}" for n in tracked()
            if n.endswith(CODE) and n not in RECORDS
            for i, l in lines(n) if HISTORY.search(l)]
    assert not hits, "이력 어투: " + ", ".join(hits[:10])


def test_이름에_판이나_임시_표시를_안_붙인다():
    hits = [f"{n}:{i}" for n in tracked() if n.endswith(".py")
            for i, l in lines(n) if VERSIONED.search(l)]
    assert not hits, "이름: " + ", ".join(hits[:10])
