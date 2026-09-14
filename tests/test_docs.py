"""문서와 사용법이 코드와 같은지 본다.

사람이 읽어서 맞추면 코드를 고칠 때마다 어긋난다. 플래그, 숫자, 상태 이름, 크기, 경로를
코드에서 읽어 문서와 견준다. 문구를 바꿔 아래 표의 패턴이 안 맞으면 표도 같이 고친다.
"""
import ast
import glob
import os
import re
import sys

import grid

ROOT = grid.ROOT
PLMI = os.path.join(ROOT, "plmi")
sys.path.insert(0, PLMI)

FLAG = re.compile(r"(?<![\w-])(-{1,2}[a-z][a-z-]*)")


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def docstring(rel):
    return ast.get_docstring(ast.parse(read(rel)), clean=False) or ""


def usage_flags(rel):
    """모듈 설명의 `python3 <이 파일>` 사용법 줄에 적힌 플래그."""
    out = set()
    for line in docstring(rel).split("\n"):
        m = re.match(r"\s+python3 (\S+)(.*)$", line)
        if m and m.group(1).endswith(os.path.basename(rel)):
            out |= set(FLAG.findall(m.group(2)))
    return out


def argv_flags(rel):
    """`"--x" in sys.argv` 나 `"--x" in args` 로 읽는 플래그."""
    return set(re.findall(r"[\"'](-{1,2}[a-z][a-z-]*)[\"']\s+in\s+(?:sys\.argv|args)", read(rel)))


def parser_flags(module):
    return {s for act in module.parser()._actions for s in act.option_strings
            if s.startswith("--") and s != "--help"}


def test_사용법_줄의_플래그가_코드와_같다():
    import install
    cases = {
        "plmi/install.py": parser_flags(install),
        "plmi/anim.py": argv_flags("plmi/anim.py"),
        "plmi/dot.py": argv_flags("plmi/dot.py"),
        "plmi/state.py": argv_flags("plmi/state.py"),
        "tests/run.py": argv_flags("tests/run.py"),
    }
    for rel, code in cases.items():
        told = usage_flags(rel)
        assert told == code, f"{rel}: 사용법에만 {sorted(told - code)}, 코드에만 {sorted(code - told)}"


def test_README_의_플래그가_설치기와_같다():
    """검사 명령 줄은 run.py 의 플래그와, 나머지는 설치기의 플래그와 견준다."""
    import install
    lines = read("README.md").split("\n")
    told = {f for l in lines if "tests/" not in l for f in FLAG.findall(l)}
    code = parser_flags(install)
    assert told == code, f"README 에만 {sorted(told - code)}, 설치기에만 {sorted(code - told)}"
    runner = {f for l in lines if "tests/run.py" in l for f in FLAG.findall(l)}
    assert runner <= argv_flags("tests/run.py"), f"run.py 에 없는 플래그: {sorted(runner - argv_flags('tests/run.py'))}"


def test_상태_이름이_어디서나_같다():
    import install
    import statusline
    readme = read("README.md")
    table = readme[readme.index("### 상태"):].split("\n\n")[1]
    in_table = re.findall(r"^\| (\S+) \|", table, re.M)[1:]          # 첫 줄은 머리
    anim = re.findall(r'^\s+"(\S+)": \(\d+, spec\(', read("plmi/anim.py"), re.M)
    dump = re.search(r"ORDER = \[(.*?)\]", read("plmi/dump_frames.py")).group(1)
    found = {
        "README 상태 표": in_table,
        "anim.py 의 anims": anim,
        "dump_frames.py 의 ORDER": re.findall(r'"(\S+?)"', dump),
        "구운 파일": sorted(install.STATES),
    }
    for where, names in found.items():
        assert sorted(names) == sorted(grid.STATES), f"{where}: {names}"
    assert statusline.RHYTHM.keys() <= set(grid.STATES), statusline.RHYTHM.keys()


def test_크기_목록이_구운_것과_같다():
    import statusline
    sizes = grid.sizes()
    readme = read("README.md")
    listed = re.search(r"크기는 ([\dx, ]+) 네 가지를 구워 둔다", readme)
    assert listed, "README 에 크기 목록 문장이 없다"
    assert [s.strip() for s in listed.group(1).split(",")] == sizes, listed.group(1)
    assert len(sizes) == 4, sizes
    default = re.search(r"기본 크기 (\d+x(\d+)) 은 (\d+)줄이다", readme)
    assert default and default.group(1) == statusline.default_size(), default and default.group(1)
    assert default.group(2) == default.group(3), default.group(0)


KOR = {"한": 1, "두": 2, "세": 3, "네": 4}


def _numbers():
    """(파일, 한 번만 나와야 하는 패턴, 코드에서 읽은 값). 패턴의 첫 무리가 그 값이다."""
    import install
    import play
    import statusline
    preview = next(a.const for a in install.parser()._actions if "--preview" in a.option_strings)
    return [
        ("README.md", r"끝 (\d+)KB 부터", statusline.TAIL / 1024),
        ("README.md", r"(\d+)MB 까지 넓혀", statusline.TAIL_MAX / (1 << 20)),
        ("plmi/statusline.py", r"끝 (\d+)KB 부터", statusline.TAIL / 1024),
        ("plmi/statusline.py", r"(\d+)MB 까지 넓힌다", statusline.TAIL_MAX / (1 << 20)),
        ("README.md", r"도구 호출 뒤 (\d+)초 넘게", statusline.FRESH),
        ("README.md", r"답을 마친 뒤 (\d+)초 동안", statusline.FRESH),
        ("README.md", r"\| (\d+)분 넘게 아무 일이", statusline.SULK / 60),
        ("README.md", r"문구는 (\d+)자에서 자른다", statusline.SAID),
        ("README.md", r"점이 (\S) 개까지 차면", statusline.DOTS),
        ("README.md", r"(\d+)초 쉬었다가 다시", statusline.TALK[2]),
        ("README.md", r"(\d+)fps 로 스스로", play.FPS),
        ("plmi/play.py", r"(\d+)fps 로 스스로", play.FPS),
        ("README.md", r"붙이지 않고 (\d+)초 돌려 본다", preview),
        ("README.md", r"(\d+)칸 이상이어야 한다", install.MIN_COLS),
        ("plmi/summary.py", r"말풍선 문구 (\d+)자 안에", statusline.SAID),
        ("plmi/statusline.py", r"가장 작은 (\d+x\d+) 에서도", grid.sizes()[-1]),
    ]


def test_문서의_숫자가_코드와_같다():
    for rel, pat, want in _numbers():
        hits = re.findall(pat, read(rel))
        assert len(hits) == 1, f"{rel}: 「{pat}」 이 {len(hits)}번 나온다. 문구를 바꿨으면 이 표도 고친다"
        got = KOR.get(hits[0], hits[0])
        if isinstance(want, str):
            assert got == want, f"{rel}: 문서 {got}, 코드 {want}"
        else:
            assert float(got) == float(want), f"{rel}: 문서 {got}, 코드 {want}"


def test_환경변수_표가_코드와_같다():
    code = set()
    for path in glob.glob(os.path.join(PLMI, "*.py")):
        with open(path, encoding="utf-8") as f:
            code |= set(re.findall(r"os\.environ\.get\(\"(PLMI_\w+)\"", f.read()))
    readme = read("README.md")
    table = set(re.findall(r"^\| `(PLMI_\w+)` \|", readme, re.M))
    assert table == code, f"표에만 {sorted(table - code)}, 코드에만 {sorted(code - table)}"


def test_구조_목록이_실제_파일과_같다():
    readme = read("README.md")
    block = re.search(r"## 구조\n\n```\n(.*?)```", readme, re.S).group(1)
    under = re.findall(r"^  (\S+)\s", block, re.M)
    listed = {n for n in under}
    real = {os.path.basename(p) for p in glob.glob(os.path.join(PLMI, "*.py"))} | {"sprites/anim/"}
    assert listed == real, f"목록에만 {sorted(listed - real)}, 실제에만 {sorted(real - listed)}"
    for top in re.findall(r"^(\S+)\s", block, re.M):
        assert os.path.exists(os.path.join(ROOT, top.rstrip("/"))), f"{top} 가 없다"


def _paths(text):
    for p in re.findall(r"`([\w./ -]+?\.(?:py|md|sh|json|rb|command|yml))`", text):
        if "/" in p and not p.startswith("~") and "*" not in p and "<" not in p:
            yield p


def test_문서가_가리키는_파일이_있다():
    sources = {"README.md": read("README.md")}
    for path in glob.glob(os.path.join(PLMI, "*.py")) + glob.glob(os.path.join(ROOT, "tests", "*.py")):
        rel = os.path.relpath(path, ROOT)
        sources[rel] = read(rel)
    missing = []
    for rel, text in sources.items():
        for p in _paths(text):
            if not (os.path.exists(os.path.join(ROOT, p)) or os.path.exists(os.path.join(PLMI, p))):
                missing.append(f"{rel}: {p}")
    assert not missing, missing
