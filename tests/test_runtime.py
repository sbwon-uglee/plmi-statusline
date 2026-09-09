"""실행 쪽이 지켜야 하는 것들. 받는 사람 컴퓨터에서 그냥 돌아야 한다."""
import json
import os
import subprocess
import sys

import grid

PLMI = os.path.join(grid.ROOT, "plmi")
RUNTIME = ("statusline.py", "bubble.py", "summary.py", "state.py", "play.py", "install.py")
SYSTEM_PY = "/usr/bin/python3"


def run(size, payload=None, py=None):
    env = dict(os.environ, PLMI_SIZE=size)
    body = json.dumps(payload or {"transcript_path": "/nonexistent"})
    out = subprocess.run([py or sys.executable, os.path.join(PLMI, "statusline.py")],
                         input=body, capture_output=True, text=True, env=env, timeout=30)
    assert out.returncode == 0, out.stderr
    return out.stdout.rstrip("\n")


def test_런타임은_표준_라이브러리만_쓴다():
    """맥 기본 파이썬에서 그냥 도는 것이 배포 조건이다. numpy 나 pillow 를 들이면 깨진다."""
    if not os.path.exists(SYSTEM_PY):
        return
    code = ("import sys; sys.path.insert(0, %r)\n" % PLMI +
            "".join(f"import {m[:-3]}\n" for m in RUNTIME))
    out = subprocess.run([SYSTEM_PY, "-c", code], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, f"{SYSTEM_PY} 에서 임포트 실패\n{out.stderr}"


def test_굽는_쪽은_런타임을_안_끌어온다():
    """statusline 이 anim 이나 dot 을 부르면 numpy 가 딸려 온다."""
    for name in RUNTIME:
        src = open(os.path.join(PLMI, name), encoding="utf-8").read()
        for bad in ("import anim", "import dot", "from anim", "from dot",
                    "import numpy", "from PIL"):
            assert bad not in src, f"{name} 이 {bad} 를 한다"


def test_모든_크기가_이름대로_줄을_낸다():
    for size in grid.sizes():
        rows = int(size.split("x")[1])
        got = run(size).split("\n")
        assert len(got) == rows, f"{size}: {len(got)}줄"


def test_대화기록이_없어도_안_죽는다():
    for size in grid.sizes():
        run(size, {"transcript_path": "/없는/파일"})
        run(size, {})


def test_말풍선이_붙어도_줄수가_그대로다():
    """말풍선은 오른쪽에 붙는다. 줄이 늘면 statusline 이 밀린다."""
    for size in grid.sizes():
        rows = int(size.split("x")[1])
        env = dict(os.environ, PLMI_SIZE=size, PLMI_BUBBLE="1")
        out = subprocess.run([sys.executable, os.path.join(PLMI, "statusline.py")],
                             input=json.dumps({"transcript_path": "/nonexistent"}),
                             capture_output=True, text=True, env=env, timeout=30)
        assert len(out.stdout.rstrip("\n").split("\n")) == rows, f"{size}"


def test_색을_끄면_escape_가_없다():
    env = dict(os.environ, PLMI_SIZE=grid.sizes()[0], PLMI_COLOR="0")
    out = subprocess.run([sys.executable, os.path.join(PLMI, "statusline.py")],
                         input=json.dumps({"transcript_path": "/nonexistent"}),
                         capture_output=True, text=True, env=env, timeout=30)
    assert "\x1b[38;2;" not in out.stdout, "PLMI_COLOR=0 인데 색이 나온다"


def test_배경색은_쓰지_않는다():
    """브라유 점이 칸을 다 채우지 않아 배경을 주면 칸 전체가 물든다. DECISIONS 참고."""
    for size in grid.sizes():
        assert "\x1b[48;2;" not in run(size), f"{size} 에 배경색 escape 가 있다"
