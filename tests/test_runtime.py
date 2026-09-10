"""실행 쪽이 지켜야 하는 것들. 받는 사람 컴퓨터에서 그냥 돌아야 한다."""
import ast
import datetime
import json
import os
import subprocess
import sys
import tempfile
import time

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
    """statusline 이 anim 이나 dot 을 부르면 numpy 가 딸려 온다.

    글자로 찾으면 다른 파이썬에 넘길 문자열까지 걸린다(install.py 가 굽기 전에 numpy 가
    깔렸는지 물어보는 자리). 실제 import 구문만 본다.
    """
    banned = {"anim", "dot", "numpy", "PIL"}
    for name in RUNTIME:
        with open(os.path.join(PLMI, name), encoding="utf-8") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                got = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                got = {(node.module or "").split(".")[0]}
            else:
                continue
            hit = got & banned
            assert not hit, f"{name} 이 {sorted(hit)} 를 임포트한다"


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

def _transcript(path, entries, ago=0.0):
    """ago 를 주면 파일이 그만큼 전에 마지막으로 자란 것처럼 만든다.

    조용한지는 항목 시각뿐 아니라 파일이 자란 시각으로도 본다. 도구 결과 한 줄이 꼬리
    창보다 커서 못 읽는 일이 있어, 못 읽은 것을 조용한 것으로 세면 안 되기 때문이다.
    """
    with open(path, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    if ago:
        when = time.time() - ago
        os.utime(path, (when, when))


def _say(role, kind, text="", ago=0.0):
    when = (datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(seconds=ago)).isoformat()
    block = {"type": kind}
    if kind == "text":
        block["text"] = text
    return {"type": role, "timestamp": when,
            "message": {"role": role, "content": [block]}}


def _tool(ago=0.0):
    when = (datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(seconds=ago)).isoformat()
    return {"type": "assistant", "timestamp": when,
            "message": {"role": "assistant", "content": [
                {"type": "tool_use", "name": "Read", "input": {"file_path": "/a"}}]}}


def test_여덟_상태가_모두_기록에서_나온다():
    """구워 두고 아무 기록으로도 안 나오는 상태가 있으면 그 그림은 죽은 것이다."""
    sys.path.insert(0, PLMI)
    import statusline

    cases = {
        "완료": [_say("assistant", "text", "다 했어", ago=1)],
        "숨쉬기": [_say("assistant", "text", "다 했어", ago=60)],
        "뾰로통": [_say("assistant", "text", "다 했어", ago=statusline.SULK + 60)],
        # 아래에서 파일 시각도 같이 늙힌다
        "놀람": [_say("user", "text", "[Request interrupted by user]", ago=1)],
        "생각중": [_say("user", "text", "이거 해줘", ago=1)],
        "작업중": [_tool(ago=0)],
        "승인대기": [_tool(ago=statusline.FRESH + 10)],
        "오류": [_tool(ago=0),
               {"type": "user", "timestamp": _say("user", "text")["timestamp"],
                "message": {"role": "user", "content": [
                    {"type": "tool_result", "is_error": True, "content": "안 됨"}]}}],
    }
    with tempfile.TemporaryDirectory() as d:
        for want, entries in cases.items():
            path = os.path.join(d, "t.jsonl")
            _transcript(path, entries,
                        ago=statusline.SULK + 60 if want == "뾰로통" else 0.0)
            got, _ = statusline.state_of(path)
            assert got == want, f"{want} 를 기대했는데 {got}"


def test_굽지_않은_크기를_불러도_안_죽는다():
    for bad in ("99x99", "abc", ""):
        env = dict(os.environ, PLMI_SIZE=bad)
        out = subprocess.run([sys.executable, os.path.join(PLMI, "statusline.py")],
                             input=json.dumps({"transcript_path": "/없음"}),
                             capture_output=True, text=True, env=env, timeout=30)
        assert out.returncode == 0, f"{bad!r} 에서 종료 {out.returncode}"
        assert out.stdout.strip(), f"{bad!r} 에서 아무것도 안 나왔다"


def test_기본_크기는_구워_둔_것에서_고른다():
    """글자로 박아 두면 굽는 줄 수가 바뀔 때마다 없는 크기가 된다.

    함수만 보면 안 된다. 실제로 쓰이는 것은 모듈이 읽어 둔 SIZE 라, PLMI_SIZE 를 지운
    자리에서 그 값을 물어야 한다.
    """
    env = {k: v for k, v in os.environ.items() if k != "PLMI_SIZE"}
    code = (f"import sys; sys.path.insert(0, {PLMI!r})\n"
            "import statusline; print(statusline.SIZE)")
    out = subprocess.run([sys.executable, "-c", code],
                         capture_output=True, text=True, env=env, timeout=30)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() in grid.sizes(), out.stdout.strip()

def test_큰_줄이_끝에_와도_판정할_것을_찾는다():
    """도구 결과 한 줄이 꼬리 창보다 클 때가 있다(실측 66,684 대 32,768바이트).

    그런 줄이 끝에 오면 고정 창에는 성한 줄이 거의 안 남아 판정이 아무것도 못 찾고
    숨쉬기로 떨어진다. 일하는 중에 가만히 있는 얼굴이 나온다.
    """
    sys.path.insert(0, PLMI)
    import statusline
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.jsonl")
        talk = [_say("assistant", "text", "무슨 말", ago=10) for _ in range(5)]
        huge = {"type": "user", "timestamp": _say("user", "text")["timestamp"],
                "message": {"role": "user", "content": [
                    {"type": "tool_result", "content": "x" * (statusline.TAIL * 2)}]}}
        _transcript(path, talk + [huge])
        ev = statusline.tail(path)
        usable = sum(len(statusline.blocks(e)) for e in ev)
        assert usable >= statusline.NEED, f"쓸 블록이 {usable}개뿐이다"
        got, _ = statusline.state_of(path)
        assert got == "작업중", got


def test_사람_말이_문자열로_와도_본다():
    """content 가 list 가 아니라 문자열로 오는 항목이 있다. 통째로 안 보였다."""
    sys.path.insert(0, PLMI)
    import statusline
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.jsonl")
        when = datetime.datetime.now(datetime.timezone.utc).isoformat()
        _transcript(path, [{"type": "user", "timestamp": when,
                            "message": {"role": "user", "content": "이거 해줘"}}])
        got, _ = statusline.state_of(path)
        assert got == "생각중", got
