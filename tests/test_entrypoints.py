"""실행할 수 있는 파일은 모두 한 번씩 실제로 돌려 본다.

`if __name__ == "__main__":` 이 있는 파이썬 파일과 셸 스크립트를 찾아, 아래 표에 돌려 보는 법이
적혀 있는지 본다. 새 진입점을 만들고 표에 안 적으면 실패한다. 표에서 다른 검사를 가리키면 그
검사가 실제로 있어야 한다.
"""
import glob
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import grid

ROOT = grid.ROOT
PLMI = os.path.join(ROOT, "plmi")


def _run(cmd, python, **kw):
    return subprocess.run([python] + cmd, capture_output=True, text=True, timeout=60, **kw)


def smoke_statusline(python):
    size = grid.sizes()[-1]
    env = dict(os.environ, PLMI_SIZE=size)
    for cmd, stdin in (([os.path.join(PLMI, "statusline.py")], "{}"),
                       ([os.path.join(PLMI, "statusline.py"), "완료", "끝"], None)):
        out = _run(cmd, python, input=stdin, env=env)
        assert out.returncode == 0 and out.stderr == "", out.stderr[-300:]
        assert len(out.stdout.rstrip("\n").split("\n")) == int(size.split("x")[1]), out.stdout[:80]


def smoke_bubble(python):
    out = _run([os.path.join(PLMI, "bubble.py"), "파일 읽는 중", "작업중"], python)
    assert out.returncode == 0 and "◀" in out.stdout, out.stderr[-300:]
    assert "파일 읽는 중" in out.stdout, "준 문구가 안 나왔다"
    bare = _run([os.path.join(PLMI, "bubble.py")], python)
    assert bare.returncode == 0 and "다음 할 일 정리 중" in bare.stdout, bare.stderr[-300:]
    one = _run([os.path.join(PLMI, "bubble.py"), "하나만 준 문구"], python)
    assert one.returncode == 0 and "하나만 준 문구" in one.stdout, one.stderr[-300:]
    arts = {}
    for state in ("숨쉬기", "놀람"):
        shown = _run([os.path.join(PLMI, "bubble.py"), "같은 문구", state], python)
        arts[state] = [l[:8] for l in shown.stdout.split("\n") if l[:1] and 0x2800 <= ord(l[0]) <= 0x28FF]
    assert arts["숨쉬기"] != arts["놀람"], "상태를 줘도 같은 그림이다"


def smoke_state(python):
    with tempfile.TemporaryDirectory() as d:
        shutil.copytree(PLMI, os.path.join(d, "plmi"), ignore=shutil.ignore_patterns("anim", "__pycache__"))
        out = _run([os.path.join(d, "plmi", "state.py"), "작업중", "시트 여는 중", "--hold", "2"], python)
        assert out.returncode == 0, out.stderr[-300:]
        with open(os.path.join(d, "plmi", "sprites", "state.json"), encoding="utf-8") as f:
            s = json.load(f)
        assert (s["state"], s["text"]) == ("작업중", "시트 여는 중") and s["until"] > 0, s


def smoke_play(python):
    out = _run([os.path.join(PLMI, "play.py"), "0.3"], python)
    assert out.returncode == 0, out.stderr[-300:]
    assert any(0x2800 <= ord(c) <= 0x28FF for c in out.stdout), "그림이 안 찍혔다"


def smoke_install(python):
    out = _run([os.path.join(PLMI, "install.py"), "--version"], python)
    assert out.returncode == 0 and out.stdout.strip(), out.stderr[-300:]
    with tempfile.TemporaryDirectory() as d:
        out = _run([os.path.join(PLMI, "install.py"), "--scope", "project", "--dir", d, "--dry-run"], python,
                   env=dict(os.environ, COLUMNS="200", LINES="60"))
        assert out.returncode == 0 and not os.listdir(d), out.stderr[-300:]


def smoke_dump_frames(python):
    with tempfile.TemporaryDirectory() as d:
        out = _run([os.path.join(PLMI, "dump_frames.py"), d], python)
        assert out.returncode == 0, out.stderr[-300:]
        page = glob.glob(os.path.join(d, "*.html"))
        assert len(page) == 1, os.listdir(d)
        with open(page[0], encoding="utf-8") as f:
            assert f.read().startswith("<!doctype html>")


def smoke_dot(python):
    import test_bake
    cmd = test_bake.baker() + [os.path.join(PLMI, "dot.py"), os.path.join(ROOT, "assets", "plmi_smile.png"), "16", "8"]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-300:]
    assert len(out.stdout.rstrip("\n").split("\n")) == 8, out.stdout


def smoke_command(python):
    path = os.path.join(ROOT, "플밍이창.command")
    if not shutil.which("zsh"):
        raise grid.Skip("zsh 가 없다")
    out = subprocess.run(["zsh", "-n", path], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    with open(path, encoding="utf-8") as f:
        body = f.read()
    assert "plmi/play.py" in body and os.path.exists(os.path.join(PLMI, "play.py")), body


# 경로 -> (돌려 보는 함수, 파이썬마다 돌리나), "모듈.검사" 로 다른 검사를 가리키기, "CI" 나 "손으로"
ENTRY = {
    "plmi/statusline.py": (smoke_statusline, True),
    "plmi/bubble.py": (smoke_bubble, True),
    "plmi/state.py": (smoke_state, True),
    "plmi/play.py": (smoke_play, True),
    "plmi/install.py": (smoke_install, True),
    "plmi/dump_frames.py": (smoke_dump_frames, False),
    "plmi/dot.py": (smoke_dot, False),
    "plmi/anim.py": "test_bake.test_다시_구우면_저장소_스프라이트와_같다",
    "build.sh": "test_bake.test_굽기가_실패하면_build_sh_가_스프라이트를_그대로_둔다",
    "플밍이창.command": (smoke_command, False),
    "tests/run.py": "test_entrypoints.test_검사_묶음이_스스로_돈다",
    "tests/mutate.py": "CI",
}
# 다른 검사 모듈이 ENTRY 를 두면 합친다. 그 저장소에만 있는 진입점을 그 모듈이 적는다
for _path in glob.glob(os.path.join(ROOT, "tests", "test_*.py")):
    _name = os.path.basename(_path)[:-3]
    if _name != __name__ and re.search(r"^ENTRY = \{", open(_path, encoding="utf-8").read(), re.M):
        ENTRY.update(importlib.import_module(_name).ENTRY)


def _entries():
    found = set()
    for path in glob.glob(os.path.join(ROOT, "**", "*.py"), recursive=True):
        rel = os.path.relpath(path, ROOT)
        if rel.startswith((".", "tests" + os.sep + "__")) or "__pycache__" in rel:
            continue
        with open(path, encoding="utf-8") as f:
            if re.search(r'^if __name__ == "__main__":', f.read(), re.M):
                found.add(rel)
    for pattern in ("*.sh", "*.command"):
        found |= {os.path.basename(p) for p in glob.glob(os.path.join(ROOT, pattern))}
    return found


def test_진입점이_모두_표에_있다():
    missing = sorted(_entries() - set(ENTRY))
    assert not missing, f"돌려 보는 법이 표에 없다: {missing}"


def test_표가_가리키는_검사가_있다():
    for rel, how in ENTRY.items():
        if isinstance(how, str) and "." in how and os.path.exists(os.path.join(ROOT, rel)):
            mod, case = how.split(".")
            assert hasattr(importlib.import_module(mod), case), f"{rel}: {how} 가 없다"


def _case(rel, fn, per_python):
    def case():
        for python in grid.PYTHONS if per_python else [sys.executable]:
            try:
                fn(python)
            except AssertionError as e:
                raise AssertionError(f"{rel} [{python}]: {e}")
    return case


for _rel, _how in ENTRY.items():
    if not isinstance(_how, str):
        globals()["test_진입점_" + _rel.replace("/", "_").replace(".", "_")] = _case(_rel, *_how)


def test_검사_묶음이_스스로_돈다():
    """run.py 가 모듈을 골라 돌리고 결과를 종료 코드로 알린다."""
    out = subprocess.run([sys.executable, os.path.join(ROOT, "tests", "run.py"), "test_layout"],
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0 and "test_layout" in out.stdout and "실패 0" in out.stdout, out.stdout[-300:]


def test_고른_돌연변이가_바꿀_문구가_파일마다_한_번씩_있다():
    """mutate.py 는 코드를 고치면 바꿀 문구를 못 찾고 멈춘다. CI 까지 가기 전에 여기서 본다."""
    import ast
    import mutate
    with open(os.path.join(ROOT, "tests", "mutate.py"), encoding="utf-8") as f:
        tree = ast.parse(f.read())
    wrong = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "swap" and len(node.args) >= 2):
            continue
        path = getattr(mutate, getattr(node.args[0], "id", ""), None)
        try:
            old = ast.literal_eval(node.args[1])
        except ValueError:
            continue                                  # cmd_line() 처럼 돌 때 정해지는 문구
        if not isinstance(path, str) or not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            count = f.read().count(old)
        if count != 1:
            wrong.append(f"{node.lineno}줄 {os.path.basename(path)} 에 {count}번: {old[:60]!r}")
    assert not wrong, "\n".join(wrong)
