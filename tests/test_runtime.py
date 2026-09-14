"""실행 쪽이 지켜야 하는 것들. 받는 사람 컴퓨터에서 그냥 돌아야 한다."""
import ast
import glob
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

import grid

PLMI = os.path.join(grid.ROOT, "plmi")
RUNTIME = ("statusline.py", "bubble.py", "summary.py", "state.py", "play.py", "install.py")
SYSTEM_PY = grid.SYSTEM_PY


def run(size, payload=None, env=None):
    full = dict(os.environ, PLMI_SIZE=size)
    # 셸에 켜 둔 값이 있으면 색이나 말풍선을 보는 검사가 빈 검사가 된다
    full.pop("PLMI_COLOR", None)
    full.pop("PLMI_BUBBLE", None)
    full.update(env or {})
    body = json.dumps({"transcript_path": "/nonexistent"} if payload is None else payload)
    out = subprocess.run([sys.executable, os.path.join(PLMI, "statusline.py")],
                         input=body, capture_output=True, text=True, env=full, timeout=30)
    assert out.returncode == 0, out.stderr
    return out.stdout.rstrip("\n")


def test_런타임은_표준_라이브러리만_쓴다():
    """맥 기본 파이썬에서 그냥 도는 것이 배포 조건이다. numpy 나 pillow 를 들이면 깨진다."""
    if not os.path.exists(SYSTEM_PY):
        raise grid.Skip(f"{SYSTEM_PY} 가 없다")
    code = ("import sys; sys.path.insert(0, %r)\n" % PLMI +
            "".join(f"import {m[:-3]}\n" for m in RUNTIME))
    out = subprocess.run([SYSTEM_PY, "-c", code], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, f"{SYSTEM_PY} 에서 임포트 실패\n{out.stderr}"


def test_런타임은_굽는_쪽을_안_끌어온다():
    """statusline 쪽이 anim 이나 dot 을 부르면 numpy 가 딸려 온다.

    import 구문만 보므로 install.py 가 다른 파이썬에 넘기는 `import numpy, PIL` 문자열은
    걸리지 않는다.
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
    """말풍선은 오른쪽에 붙는다. 문구가 길어 줄이 늘면 statusline 이 밀린다."""
    long = "시트 여러 장을 차례로 열어 값을 옮기고 합계를 다시 맞춘 뒤 결과를 표 하나로 정리해 보고서에 붙이는 중"
    for size in grid.sizes():
        rows = int(size.split("x")[1])
        env = dict(os.environ, PLMI_SIZE=size, PLMI_BUBBLE="1", PLMI_COLOR="0")
        out = subprocess.run([sys.executable, os.path.join(PLMI, "statusline.py"), "작업중", long],
                             capture_output=True, text=True, env=env, timeout=30)
        assert "\u25c0" in out.stdout, f"{size}: 말풍선이 안 떴다"
        got = len(out.stdout.rstrip("\n").split("\n"))
        assert got == rows, f"{size}: {got}줄"


def test_색을_끄면_escape_가_없다():
    assert "\x1b[38;2;" not in run(grid.sizes()[0], env={"PLMI_COLOR": "0"}), \
        "PLMI_COLOR=0 인데 색이 나온다"


def test_배경색은_쓰지_않는다():
    """브라유 점이 칸을 다 채우지 않아 배경을 주면 칸 전체가 물든다."""
    for size in grid.sizes():
        assert "\x1b[48;2;" not in run(size), f"{size} 에 배경색 escape 가 있다"


def _transcript(path, entries, ago=0.0):
    """entries 를 jsonl 로 쓴다. ago 를 주면 파일 수정 시각을 그만큼 앞당긴다."""
    with open(path, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    if ago:
        when = time.time() - ago
        os.utime(path, (when, when))


def _when(ago=0.0):
    return (datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(seconds=ago)).isoformat()


def _say(role, text="", ago=0.0):
    return {"type": role, "timestamp": _when(ago),
            "message": {"role": role, "content": [{"type": "text", "text": text}]}}


def _tool(ago=0.0, name="Read"):
    return {"type": "assistant", "timestamp": _when(ago),
            "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "u1", "name": name, "input": {"file_path": "/a"}}]}}


def test_여덟_상태가_모두_기록에서_나온다():
    """구워 두고 아무 기록으로도 안 나오는 상태가 있으면 그 그림은 죽은 것이다."""
    sys.path.insert(0, PLMI)
    import statusline

    cases = {
        "완료": [_say("assistant", "다 했어", ago=1)],
        "숨쉬기": [_say("assistant", "다 했어", ago=60)],
        "뾰로통": [_say("assistant", "다 했어", ago=statusline.SULK + 60)],  # 파일 시각도 아래에서 같이 늙힌다
        "놀람": [_say("user", "[Request interrupted by user]", ago=1)],
        "생각중": [_say("user", "이거 해줘", ago=1)],
        "작업중": [_tool(ago=0)],
        "승인대기": [_tool(ago=statusline.FRESH + 10, name="Bash")],
        "오류": [_tool(ago=0),
               {"type": "user", "timestamp": _when(),
                "message": {"role": "user", "content": [
                    {"type": "tool_result", "is_error": True, "content": "안 됨"}]}}],
    }
    with tempfile.TemporaryDirectory() as d:
        for want, entries in cases.items():
            path = os.path.join(d, "t.jsonl")
            _transcript(path, entries,
                        ago=statusline.SULK + 60 if want == "뾰로통" else 0.0)
            got = statusline.state_of(path)[0]
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
    """글자로 박아 두면 굽는 줄 수가 바뀔 때마다 없는 크기가 된다. PLMI_SIZE 를 지운 채 모듈의 SIZE 를 본다."""
    env = {k: v for k, v in os.environ.items() if k != "PLMI_SIZE"}
    code = (f"import sys; sys.path.insert(0, {PLMI!r})\n"
            "import statusline; print(statusline.SIZE)")
    out = subprocess.run([sys.executable, "-c", code],
                         capture_output=True, text=True, env=env, timeout=30)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() in grid.sizes(), out.stdout.strip()


def test_큰_줄이_끝에_와도_판정할_것을_찾는다():
    """도구 결과 한 줄이 꼬리 창보다 커도 판정할 블록을 찾는다. 못 찾으면 일하는 중에 숨쉬기가 뜬다."""
    sys.path.insert(0, PLMI)
    import statusline
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.jsonl")
        talk = [_say("assistant", "무슨 말", ago=10) for _ in range(5)]
        huge = {"type": "user", "timestamp": _when(),
                "message": {"role": "user", "content": [
                    {"type": "tool_result", "content": "x" * (statusline.TAIL * 2)}]}}
        _transcript(path, talk + [huge])
        ev = statusline.tail(path)
        usable = sum(len(statusline.blocks(e)) for e in ev)
        assert usable >= statusline.NEED, f"쓸 블록이 {usable}개뿐이다"
        got = statusline.state_of(path)[0]
        assert got == "생각중", got


def test_사람_말이_문자열로_와도_본다():
    """사람 말의 content 가 문자열로 와도 생각중이 뜬다."""
    sys.path.insert(0, PLMI)
    import statusline
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.jsonl")
        _transcript(path, [{"type": "user", "timestamp": _when(),
                            "message": {"role": "user", "content": "이거 해줘"}}])
        got = statusline.state_of(path)[0]
        assert got == "생각중", got


def test_오래_쉬면_심심하다고_한다():
    """15분 넘게 조용하면 뾰로통이 되고 심심해라고 한다."""
    sys.path.insert(0, PLMI)
    import statusline
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.jsonl")
        _transcript(path, [_say("assistant", "다 했어",
                                ago=statusline.SULK + 60)],
                    ago=statusline.SULK + 60)
        state, said, _ = statusline.state_of(path)
        assert state == "뾰로통", state
        assert said == "심심해", said


ESC = re.compile(r"\x1b\[[0-9;]*m")
BOX = set("╭╮╰╯─│◀")


def _speech(name, text, at, since=1000.0):
    """말을 꺼낸 지 at 초 뒤의 (말풍선에 보이는 글자, 줄마다 칸 수).

    말풍선이 없으면 글자 자리가 None 이다. since 가 None 이면 at 을 벽시계로 쓴다.
    """
    sys.path.insert(0, PLMI)
    import statusline
    from bubble import cells
    keep, statusline.BUBBLE = statusline.BUBBLE, True
    try:
        art = statusline.panel(name, text, when=at if since is None else since + at,
                               since=since)
    finally:
        statusline.BUBBLE = keep
    lines = ESC.sub("", art).split("\n")
    if not any(c in BOX for l in lines for c in l):
        return None, [cells(l) for l in lines]
    words = "".join(c for l in lines for c in l
                    if not 0x2800 <= ord(c) <= 0x28FF and c not in BOX and not c.isspace())
    return words, [cells(l) for l in lines]


def _said(name, text, span):
    """말을 꺼낸 뒤 span 초 동안 말풍선 글자가 바뀐 차례. 말풍선이 없던 구간은 None."""
    step, seq = 0.05, []
    for k in range(int(span / step)):
        w = _speech(name, text, k * step)[0]
        if not seq or seq[-1] != w:
            seq.append(w)
    return seq


LONG = "파일 여러 개를 한꺼번에 읽어 오는 중"


def test_문구는_한꺼번에_뜨고_점이_하나씩_는다():
    """문구는 바로 다 뜨고 뒤에서 점이 하나씩 는다."""
    got = _said("뾰로통", "심심해", 5)
    assert got[:4] == ["심심해", "심심해.", "심심해..", "심심해..."], got


def test_쉴_때_불리는_간격으로_봐도_점이_하나씩_는다():
    """쉴 때는 상태줄이 초당 한 번 불린다. 점이 그보다 빨리 늘면 볼 때마다 칸을 건너뛰어
    점이 없다가 두 개였다가만 되풀이한다."""
    for name, text in (("뾰로통", "심심해"), ("놀람", "앗"), ("완료", "끝"),
                       ("승인대기", "허락 기다리는 중")):
        seen = [_speech(name, text, k + 0.3)[0] for k in range(4)]
        want = [text.replace(" ", "") + "." * n for n in range(4)]
        assert seen == want, f"{name}: {seen}"


def test_말풍선이_떠_있는_동안_상자_크기가_그대로다():
    """점이 늘 때마다 상자가 커지면 그림이 흔들린다. 긴 문구는 줄 바꿈 자리를 넘으면서
    줄 수까지 바뀐다."""
    for name, text in (("뾰로통", "심심해"), ("오류", "안 됐어"), ("작업중", LONG)):
        shapes = set()
        for k in range(300):
            words, widths = _speech(name, text, k * 0.05)
            if words is not None:
                shapes.add(tuple(widths))
        assert len(shapes) == 1, f"{name}: 상자 모양이 {len(shapes)}가지"


def test_수다는_쉬었다가_다시_말한다():
    got = _said("뾰로통", "심심해", 20)
    assert None in got, f"쉬는 틈이 없다: {got}"
    after = got[got.index(None):]
    assert "심심해" in after, f"쉰 뒤에 다시 말하지 않는다: {got}"


def test_일이_난_순간부터_말한다():
    """일이 난 순간 문구가 점 없이 뜬다. 박자는 사건 시각부터 잰다."""
    for since in (1000.0, 1004.5, 1007.25):
        for name, text in (("뾰로통", "심심해"), ("놀람", "앗"), ("작업중", LONG)):
            got = _speech(name, text, 0.0, since)[0]
            assert got == text.replace(" ", ""), f"{name} 을 꺼낸 순간 {got!r}"


def test_외치는_말은_한_번만_한다():
    """앗과 끝은 한 번만 뜬다. 놀람은 사람이 다음 말을 걸 때까지 이어진다."""
    for name, text in (("놀람", "앗"), ("완료", "끝")):
        assert _speech(name, text, 0.0)[0] == text
        for at in (10.0, 60.0, 600.0):
            assert _speech(name, text, at)[0] is None, f"{at}초 뒤에도 {text}"


def test_일하는_중에는_말풍선이_안_사라진다():
    """지금 무슨 일인지 알려 주는 문구다. 쉬는 틈에 보면 무슨 일을 하는지 모른다."""
    for name in ("작업중", "생각중", "승인대기"):
        for k in range(300):
            assert _speech(name, LONG, k * 0.1)[0] is not None, f"{name} {k * 0.1:.1f}초"


def test_언제_꺼낸_말인지_몰라도_보인다():
    """손으로 지정한 상태에는 사건 시각이 없다. 한 번만 할 말이 영영 안 보이면 안 된다.

    실제 벽시계는 17억 초쯤이다. 0 부터 재면 첫 몇 초에 한 번 말한 것이 보여 통과해 버린다.
    """
    now = 1.7e9
    seen = [_speech(name, text, now + t, since=None)[0]
            for name, text in (("놀람", "앗"), ("완료", "끝")) for t in range(30)]
    assert any(w is not None for w in seen)


def test_말을_꺼낸_시각을_기록에서_읽는다():
    sys.path.insert(0, PLMI)
    import statusline
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.jsonl")
        _transcript(path, [_say("user", "[Request interrupted by user]", ago=5)])
        name, _, since = statusline.state_of(path)
        assert name == "놀람", name
        assert since is not None and abs(time.time() - 5 - since) < 1, since
        _transcript(path, [_say("assistant", "다 했어", ago=statusline.SULK + 60)],
                    ago=statusline.SULK + 60)
        name, _, since = statusline.state_of(path)
        assert name == "뾰로통", name
        # 조용해진 지 SULK 만큼 지난 순간, 곧 60초 전에 심심해졌다
        assert since is not None and abs(time.time() - 60 - since) < 1, since


def test_창은_어느_워크스페이스의_대화든_따라간다():
    """창 실행기는 plmi 가 깔린 자리와 상관없이 모든 워크스페이스에서 가장 최근 대화 기록을 고른다."""
    sys.path.insert(0, PLMI)
    import play
    keep = os.environ.get("HOME")
    with tempfile.TemporaryDirectory() as d:
        older = os.path.join(d, ".claude", "projects", "-some-work", "a.jsonl")
        newer = os.path.join(d, ".claude", "projects", "-other-work", "b.jsonl")
        for path, ago in ((older, 60), (newer, 5)):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            open(path, "w").close()
            when = time.time() - ago
            os.utime(path, (when, when))
        os.environ["HOME"] = d
        try:
            got = play.newest_transcript()
        finally:
            if keep is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = keep
    assert got == newer, got


def test_도구를_돌리다_끊어도_놀란다():
    """도구를 돌리던 중에 끊으면 문구 뒤에 for tool use 가 붙는다."""
    sys.path.insert(0, PLMI)
    import statusline
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.jsonl")
        _transcript(path, [_tool(ago=3),
                           _say("user", "[Request interrupted by user for tool use]", ago=1)])
        got = statusline.state_of(path)[0]
        assert got == "놀람", got


def test_서브에이전트_도구도_문구로_바꾼다():
    sys.path.insert(0, PLMI)
    from summary import summarize
    assert summarize("Agent", {"description": "검토"}) == "검토 시키는 중"


def test_손으로_지정할_때_hold_값이_문구로_안_들어간다():
    with tempfile.TemporaryDirectory() as d:
        shutil.copytree(PLMI, os.path.join(d, "plmi"), ignore=shutil.ignore_patterns("anim"))
        subprocess.run([sys.executable, os.path.join(d, "plmi", "state.py"), "완료", "--hold", "5"],
                       check=True, capture_output=True, timeout=30)
        with open(os.path.join(d, "plmi", "sprites", "state.json"), encoding="utf-8") as f:
            s = json.load(f)
        assert (s["state"], s["text"]) == ("완료", ""), s


def test_굽지_않은_크기면_상태마다_같은_크기를_쓴다():
    """상태마다 다른 크기를 집으면 상태가 바뀔 때 상태줄 줄 수가 달라진다."""
    env = dict(os.environ, PLMI_SIZE="99x99", PLMI_BUBBLE="0", PLMI_COLOR="0")
    rows = set()
    for state in grid.STATES:
        out = subprocess.run([sys.executable, os.path.join(PLMI, "statusline.py"), state],
                             capture_output=True, text=True, env=env, timeout=30)
        rows.add(len(out.stdout.rstrip("\n").split("\n")))
    assert len(rows) == 1, f"상태마다 줄 수가 다르다: {sorted(rows)}"


def test_긴_이름을_잘라도_하는_일은_남는다():
    """말풍선 문구는 22자에서 잘린다. 이름이 길어도 뒤의 「읽는 중」 같은 말이 남아야 한다."""
    sys.path.insert(0, PLMI)
    import statusline
    from summary import summarize
    long = "very_long_file_name_for_testing.py"
    for tool, arg, verb in (("Read", {"file_path": "/a/" + long}, "읽는 중"),
                            ("Edit", {"file_path": long}, "고치는 중"),
                            ("Grep", {"pattern": long}, "찾는 중"),
                            ("Agent", {"description": long}, "시키는 중"),
                            ("mcp__srv__" + long, {}, "부르는 중")):
        said = summarize(tool, arg)
        assert len(said) <= statusline.SAID and said.endswith(verb), f"{tool}: {said!r}"


def test_앞뒤_공백이_있어도_점이_제자리에서_는다():
    """말풍선은 공백을 접어 그린다. 글자 수를 원문으로 세면 점이 미리 보인다."""
    assert _speech("작업중", " 찾는 중", 0.0)[0] == "찾는중"


def _statusline(env, stdin="{}", python=None):
    return subprocess.run([python or sys.executable, os.path.join(PLMI, "statusline.py")], input=stdin,
                          capture_output=True, text=True, env=dict(os.environ, **env), timeout=30)


def test_칸_수가_같은_크기가_둘이어도_늘_같은_크기를_고른다():
    """구운 폴더에 26x11 과 26x12 가 같이 있으면 해시 순서에 따라 고르는 크기가 바뀌면 안 된다."""
    with tempfile.TemporaryDirectory() as home:
        baked = os.path.join(home, ".claude", "plmi-sizes")
        os.makedirs(baked)
        for p in glob.glob(os.path.join(glob.escape(grid.ANIM), "플밍이_*_26x*.json")):
            name = os.path.basename(p).rsplit("_", 1)[0] + "_26x99.json"
            shutil.copy(p, os.path.join(baked, name))
        code = f"import sys; sys.path.insert(0, {PLMI!r}); import statusline; print(statusline.default_size())"
        seen = {subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30,
                               env=dict(os.environ, HOME=home, PYTHONHASHSEED=str(seed))).stdout.strip()
                for seed in range(8)}
        assert len(seen) == 1, f"씨앗마다 다른 크기를 골랐다: {seen}"


def test_구운_스프라이트가_깨져도_줄_수를_지킨다():
    size = next(s for s in grid.sizes() if s.startswith("26x"))
    rows = int(size.split("x")[1])
    with tempfile.TemporaryDirectory() as home:
        baked = os.path.join(home, ".claude", "plmi-sizes")
        os.makedirs(baked)
        for state in grid.STATES:
            with open(os.path.join(baked, f"플밍이_{state}_{size}.json"), "w") as f:
                f.write("" if state == "숨쉬기" else "{깨짐")
        out = _statusline({"HOME": home, "PLMI_SIZE": size})
        assert len(out.stdout.rstrip("\n").split("\n")) == rows, f"{out.stdout[:80]!r} {out.stderr[-200:]}"


def test_UTF_8_이_아닌_로캘에서도_상태줄이_나온다():
    size = grid.sizes()[-1]
    for python in grid.PYTHONS:
        out = _statusline({"PLMI_SIZE": size, "LC_ALL": "en_US.US-ASCII", "LANG": "C"}, python=python)
        got = out.stdout.encode("utf-8", "replace").decode("utf-8") if out.stdout else ""
        assert len(got.rstrip("\n").split("\n")) == int(size.split("x")[1]), f"[{python}] {out.stderr[-300:]}"


def test_state_py_를_동시에_불러도_둘_다_끝난다():
    with tempfile.TemporaryDirectory() as d:
        shutil.copytree(PLMI, os.path.join(d, "plmi"), ignore=shutil.ignore_patterns("anim", "__pycache__"))
        script = os.path.join(d, "plmi", "state.py")
        procs = [subprocess.Popen([sys.executable, script, "작업중", f"문구 {i}"],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE) for i in range(16)]
        codes = [p.wait(timeout=60) for p in procs]
        assert codes == [0] * 16, [p.stderr.read()[-200:] for p in procs if p.returncode]


def test_창은_기록이_고르는_사이에_지워져도_안_죽는다():
    sys.path.insert(0, PLMI)
    import play
    keep = play.glob.glob
    play.glob.glob = lambda *a, **k: ["/없는/기록.jsonl"]
    try:
        assert play.newest_transcript() == "/없는/기록.jsonl"
    finally:
        play.glob.glob = keep


def _state_copy(d):
    shutil.copytree(PLMI, os.path.join(d, "plmi"), ignore=shutil.ignore_patterns("anim", "__pycache__"))
    return os.path.join(d, "plmi")


def _read_state(plmi):
    code = f"import sys; sys.path.insert(0, {plmi!r}); import state, json; print(json.dumps(state.read(), ensure_ascii=False))"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return tuple(json.loads(out.stdout))


def test_손으로_지정한_상태를_읽고_hold_가_지나면_숨쉬기로_돌아간다():
    with tempfile.TemporaryDirectory() as d:
        plmi = _state_copy(d)
        script = os.path.join(plmi, "state.py")
        path = os.path.join(plmi, "sprites", "state.json")
        subprocess.run([sys.executable, script, "완료", "--hold", "30", "끝났어"], check=True, timeout=30)
        assert _read_state(plmi) == ("완료", "끝났어"), "hold 뒤에 온 문구를 잃었다"
        subprocess.run([sys.executable, script, "오류", "안 됐어"], check=True, timeout=30)
        with open(path, encoding="utf-8") as f:
            assert json.load(f)["until"] == 0, "hold 를 안 줬는데 풀리는 시각이 적혔다"
        assert _read_state(plmi) == ("오류", "안 됐어"), "hold 없이 지정한 상태가 풀렸다"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"state": "놀람", "text": "앗", "until": time.time() - 1}, f, ensure_ascii=False)
        assert _read_state(plmi) == ("숨쉬기", ""), "시간이 지났는데 안 풀렸다"
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"state": "놀람", "text": "앗", "until": time.time() + 60}, f, ensure_ascii=False)
        assert _read_state(plmi) == ("놀람", "앗")
        for body in ("{깨짐", json.dumps({"text": "문구만"}), json.dumps({"state": "작업중"})):
            with open(path, "w", encoding="utf-8") as f:
                f.write(body)
            got = _read_state(plmi)
            want = {"{깨짐": ("숨쉬기", ""), json.dumps({"text": "문구만"}): ("숨쉬기", "문구만"),
                    json.dumps({"state": "작업중"}): ("작업중", "")}[body]
            assert got == want, f"{body}: {got}"
        os.remove(path)
        assert _read_state(plmi) == ("숨쉬기", ""), "파일이 없는데 숨쉬기가 아니다"


def test_터미널에서_그냥_부르면_손으로_지정한_상태를_보인다():
    """stdin 이 터미널이면 세션 JSON 이 없다. 그때는 state.py 로 적어 둔 상태와 문구를 그린다."""
    import pty
    with tempfile.TemporaryDirectory() as d:
        plmi = _state_copy(d)
        shutil.copytree(grid.ANIM, os.path.join(plmi, "sprites", "anim"))
        # 완료는 몇 초 쉬었다 다시 뜨는 말이라 시각에 따라 안 보인다. 늘 떠 있는 작업중으로 본다
        subprocess.run([sys.executable, os.path.join(plmi, "state.py"), "작업중", "다 됐다"], check=True, timeout=30)
        master, slave = pty.openpty()
        try:
            out = subprocess.run([sys.executable, os.path.join(plmi, "statusline.py")], stdin=slave,
                                 capture_output=True, timeout=30,
                                 env=dict(os.environ, PLMI_SIZE=grid.sizes()[0], PLMI_COLOR="0"))
        finally:
            os.close(master)
            os.close(slave)
        shown = out.stdout.decode("utf-8")
        assert out.returncode == 0, out.stderr[-300:]
        assert "다" in shown and "됐다" in shown, f"지정한 문구가 안 나왔다: {shown[-200:]!r}"


def test_말풍선_없이_찍는_그림은_크기대로_나온다():
    sys.path.insert(0, PLMI)
    import statusline
    for name in ("숨쉬기", "없는상태", None):
        art = statusline.frame(name)
        rows = len(statusline.load("숨쉬기")["frames"][0].split("\n"))
        assert art and len(art.split("\n")) == rows, (name, art[:40])


def test_문구의_escape_와_제어_문자를_지운다():
    sys.path.insert(0, PLMI)
    import statusline
    cases = [("\x1b[31m빨강\x1b[0m", "빨강"), ("탭\t끝", "탭 끝"), ("a\x00b", "a b"), ("그대로", "그대로"),
             ("\x1b[2K지움", "지움"), (3, "3")]
    wrong = [(raw, statusline.clean(raw), want) for raw, want in cases if statusline.clean(raw) != want]
    assert not wrong, wrong


def test_PLMI_BUBBLE_이_0_이면_말풍선이_없다():
    size = grid.sizes()[-1]
    for value, shown in (("0", False), ("1", True), ("", True)):
        out = subprocess.run([sys.executable, os.path.join(PLMI, "statusline.py"), "작업중", "읽는 중"],
                             capture_output=True, text=True, timeout=30,
                             env=dict(os.environ, PLMI_SIZE=size, PLMI_BUBBLE=value))
        assert ("◀" in out.stdout) == shown, (value, out.stdout[-120:])


def test_세션_JSON_이_안_와도_기다리지_않는다():
    """stdin 이 열린 채 아무것도 안 오면 조금만 보고 손으로 지정한 상태로 넘어간다."""
    proc = subprocess.Popen([sys.executable, os.path.join(PLMI, "statusline.py")], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env=dict(os.environ, PLMI_SIZE=grid.sizes()[-1]))
    try:
        start = time.time()
        while proc.poll() is None and time.time() - start < 3:
            time.sleep(0.05)
        assert proc.poll() is not None, "세션 JSON 을 기다리며 멈춰 있다"
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.communicate()


def test_긴_대화_기록도_끝만_읽는다():
    """판정이 읽은 바이트를 세어 창 한도를 안 넘는지 본다. 시간으로 재면 바쁜 컴퓨터에서 흔들린다."""
    sys.path.insert(0, PLMI)
    import statusline
    read = []

    class Counting:
        def __init__(self, f):
            self.f = f

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.f.close()

        def __getattr__(self, name):
            return getattr(self.f, name)

        def read(self, *args):
            data = self.f.read(*args)
            read.append(len(data))
            return data

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.jsonl")
        line = json.dumps(_say("assistant", "지난 말", ago=100), ensure_ascii=False) + "\n"
        with open(path, "w", encoding="utf-8") as f:
            f.write(line * ((statusline.TAIL_MAX + (4 << 20)) // len(line)))
            f.write(json.dumps(_tool(ago=0), ensure_ascii=False) + "\n")
        statusline.open = lambda *a, **k: Counting(open(*a, **k))
        try:
            got = statusline.state_of(path)
        finally:
            del statusline.open
    assert got[0] == "작업중", got
    assert read and max(read) <= statusline.TAIL, f"한 번에 {max(read)}바이트를 읽었다. 끝 창만 읽어야 한다"


def test_색은_칸마다_바뀔_때만_찍고_줄_끝에서_되돌린다():
    sys.path.insert(0, PLMI)
    import statusline
    a = grid.load("작업중", grid.sizes()[0])
    tint = a["tints"][0]
    lines = a["frames"][0].split("\n")
    out = statusline.tinted(lines, tint, a["palette"], a["cw"])
    for line, row, got in zip(lines, tint.split("\n"), out):
        runs, prev = 0, None
        for key in row:
            if key != prev and key != ".":
                runs += 1
            prev = key
        assert got.count("\x1b[38;2;") == runs, (row, got.count("\x1b[38;2;"), runs)
        # 칸마다 그 칸에 걸린 색이 tint 대로인지 escape 를 따라가며 본다. 줄 끝에는 색이 풀려 있어야 한다
        color, cell = None, 0
        for m in re.finditer(r"\x1b\[([0-9;]*)m|(.)", got, re.S):
            if m.group(1) is not None:
                color = None if m.group(1) == "0" else m.group(1)
                continue
            key = row[cell] if cell < len(row) else "."
            want = None if key == "." else "38;2;{};{};{}".format(*a["palette"][statusline.CHARS.index(key)])
            assert color == want, f"{cell}번 칸 색 {color}, 기대 {want}"
            cell += 1
        assert color is None, f"색이 줄 끝에서 안 풀린다: {got[-12:]!r}"
    colored = subprocess.run([sys.executable, os.path.join(PLMI, "statusline.py"), "작업중"],
                             capture_output=True, text=True, timeout=30,
                             env=dict(os.environ, PLMI_SIZE=grid.sizes()[0]))
    assert "\x1b[38;2;" in colored.stdout, "색을 켰는데 칠하지 않았다"


def test_일하는_중_점은_박자마다_하나씩_늘고_세_개_뒤에_처음으로_돌아간다():
    sys.path.insert(0, PLMI)
    import statusline
    beat = statusline.RHYTHM["작업중"][0]
    seen = [_speech("작업중", "읽는 중", beat * k + beat / 2)[0] for k in range(statusline.DOTS + 2)]
    want = ["읽는중" + "." * n for n in range(statusline.DOTS + 1)] + ["읽는중"]
    assert seen == want, seen


def test_장은_hold_나_cycle_에_맞춰_고른다():
    sys.path.insert(0, PLMI)
    import statusline
    keep = statusline.COLOR, statusline.BUBBLE
    statusline.COLOR, statusline.BUBBLE = False, False
    try:
        rest = dict(statusline.load("숨쉬기"), hold=0.5)     # 1 이 아닌 hold 로 봐야 곱셈과 나눗셈이 갈린다
        statusline._cache["숨쉬기"] = rest
        for k in range(len(rest["frames"]) + 2):
            t = 1000 * rest["hold"] + (k + 0.5) * rest["hold"]
            want = rest["frames"][int(t / rest["hold"]) % len(rest["frames"])]
            assert statusline.panel("숨쉬기", when=t) == want, k
        work = statusline.load("작업중")
        n = len(work["frames"])
        for k in range(n + 2):
            t = 1000 * statusline.CYCLE + (k + 0.5) * statusline.CYCLE / n
            assert statusline.panel("작업중", when=t) == work["frames"][int(t * n / statusline.CYCLE) % n], k
            assert statusline.panel("작업중", when=t, cycle=None) == work["frames"][int(t * work["fps"]) % n], k
    finally:
        statusline.COLOR, statusline.BUBBLE = keep
        statusline._cache.clear()


def test_줄_끝_칸에_색이_있으면_줄_끝에서_색을_푼다():
    """지금 스프라이트는 줄 끝 칸이 늘 비어 있다. 끝까지 색이 찬 줄을 직접 만들어 본다."""
    sys.path.insert(0, PLMI)
    import statusline
    palette = [[1, 2, 3], [4, 5, 6]]
    got = statusline.tinted(["\u28ff\u28ff\u28ff"], "001", palette, 3)[0]
    assert got == "\x1b[0m\x1b[38;2;1;2;3m\u28ff\u28ff\x1b[0m\x1b[38;2;4;5;6m\u28ff\x1b[0m", repr(got)
    # 끝 칸이 비었으면 색은 이미 풀렸으니 줄 끝에 더 안 붙인다
    got = statusline.tinted(["\u28ff\u28ff"], "0.", palette, 2)[0]
    assert got == "\x1b[0m\x1b[38;2;1;2;3m\u28ff\x1b[0m\u28ff", repr(got)


def test_말풍선에는_색을_안_칠한다():
    sys.path.insert(0, PLMI)
    import statusline
    keep = statusline.COLOR, statusline.BUBBLE, statusline.SIZE
    statusline.COLOR, statusline.BUBBLE = True, True
    try:
        art = statusline.panel("작업중", "읽는 중", when=5.0, since=5.0)
        cw = statusline.load("작업중")["cw"]
        for line in art.split("\n"):
            cells, i, tail = 0, 0, None
            while i < len(line):
                m = re.match(r"\x1b\[[0-9;]*m", line[i:])
                if m:
                    i += m.end()
                    continue
                cells += 1
                i += 1
                if cells == cw:
                    tail = line[i:]
                    break
            if tail:
                assert "\x1b[38;2;" not in tail, f"말풍선 쪽에 색이 있다: {tail[:30]!r}"
    finally:
        statusline.COLOR, statusline.BUBBLE, statusline.SIZE = keep


def test_크기는_칸_수_순서로_늘어서고_기본은_26칸이다():
    with tempfile.TemporaryDirectory() as home:
        baked = os.path.join(home, ".claude", "plmi-sizes")
        os.makedirs(baked)
        for fake in ("30x5", "27x40"):
            for p in glob.glob(os.path.join(glob.escape(grid.ANIM), "플밍이_*_26x*.json")):
                shutil.copy(p, os.path.join(baked, os.path.basename(p).rsplit("_", 1)[0] + f"_{fake}.json"))
        code = (f"import sys; sys.path.insert(0, {PLMI!r}); import statusline; "
                "print(','.join(statusline.sizes())); print(statusline.default_size())")
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30,
                             env=dict(os.environ, HOME=home)).stdout.split("\n")
    cols = [int(s.split("x")[0]) for s in out[0].split(",")]
    assert cols == sorted(cols, reverse=True), out[0]
    assert out[1].startswith("26x"), out[1]


def test_받는_쪽이_먼저_닫아도_오류를_안_찍는다():
    proc = subprocess.Popen([sys.executable, os.path.join(PLMI, "statusline.py"), "작업중", "읽는 중"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env=dict(os.environ, PLMI_SIZE=grid.sizes()[0]))
    proc.stdout.close()
    err = proc.stderr.read().decode("utf-8", "replace")
    proc.wait(timeout=30)
    assert "BrokenPipe" not in err and "Exception" not in err, err[-300:]


def test_인자로_상태와_문구를_주면_그대로_그린다():
    size = grid.sizes()[0]
    env = dict(os.environ, PLMI_SIZE=size, PLMI_COLOR="0")
    def run(*args):
        return subprocess.run([sys.executable, os.path.join(PLMI, "statusline.py"), *args],
                              capture_output=True, text=True, timeout=30, env=env).stdout
    rows = int(size.split("x")[1])
    one = run("놀람")
    assert len(one.rstrip("\n").split("\n")) == rows and "◀" not in one, one[-80:]
    assert run("놀람") != run("숨쉬기"), "상태를 무시했다"
    two = run("작업중", "시트 여는 중")
    assert "시트" in two and len(two.rstrip("\n").split("\n")) == rows, two[-80:]


def test_조용한지는_기록_시각과_파일_시각_중_최근_것으로_본다():
    sys.path.insert(0, PLMI)
    import statusline
    old = statusline.SULK + 60
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.jsonl")
        _transcript(path, [_say("assistant", "다 했어", ago=old)])               # 파일은 방금 자랐다
        assert statusline.state_of(path)[0] != "뾰로통", "파일이 방금 자랐는데 뾰로통하다"
        _transcript(path, [_say("assistant", "다 했어", ago=1)], ago=old)       # 파일 시각만 오래됐다
        assert statusline.state_of(path)[0] != "뾰로통", "방금 쓴 항목이 있는데 뾰로통하다"


def test_대신_찍는_그림은_벽시계와_fps_로_장을_고른다():
    sys.path.insert(0, PLMI)
    import statusline

    class Clock:
        now = 0.0

        def time(self):
            return self.now

    keep, clock = statusline.time, Clock()
    statusline.time = clock
    try:
        a = statusline.load("작업중")
        n = len(a["frames"])
        for k in range(n + 2):
            clock.now = 1000.0 + (k + 0.5) / a["fps"]
            assert statusline.frame("작업중") == a["frames"][int(clock.now * a["fps"]) % n], k
    finally:
        statusline.time = keep


def test_그리다가_예외가_나면_말풍선_없는_그림으로_물러난다():
    """판정이나 그리기에서 예상 못 한 예외가 나도 상태줄이 비지 않는다. 깨진 hold 값으로 그 길을 탄다."""
    with tempfile.TemporaryDirectory() as home:
        baked = os.path.join(home, ".claude", "plmi-sizes")
        os.makedirs(baked)
        with open(os.path.join(baked, "플밍이_숨쉬기_9x1.json"), "w", encoding="utf-8") as f:
            json.dump({"frames": ["⣿"], "tints": ["."], "palette": [], "cw": 1, "fps": 1, "hold": "깨짐"}, f)
        out = subprocess.run([sys.executable, os.path.join(PLMI, "statusline.py")], input="{}",
                             capture_output=True, text=True, timeout=30,
                             env=dict(os.environ, HOME=home, PLMI_SIZE="9x1"))
    assert out.stdout == "⣿\n", (out.stdout, out.stderr[-300:])
