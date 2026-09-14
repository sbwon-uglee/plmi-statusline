"""실행 쪽을 무작위 입력으로 두드려 늘 지켜야 하는 성질을 본다.

사람이 떠올린 입력 몇 개만 보면 그 밖에서 깨진다. 대화 기록, 문구, 크기, 시각을 씨앗으로
만들고, 실패하면 씨앗을 메시지에 남겨 그대로 다시 돌릴 수 있게 한다.
반복 수는 `run.py --deep` 에서 스무 배가 된다.
"""
import datetime
import json
import os
import random
import re
import subprocess
import sys
import tempfile
import time

import grid

PLMI = os.path.join(grid.ROOT, "plmi")
sys.path.insert(0, PLMI)
import bubble  # noqa: E402
import statusline  # noqa: E402
import summary  # noqa: E402

N = grid.times(80)
SGR = re.compile(r"\x1b\[[0-9;]*m")
WIDE = chr(0xAC00)                       # 한글 한 글자. 터미널에서 두 칸
EMOJI = chr(0x1F600)
TEXTS = ["", " ", "끝", "다음 할 일 정리 중", "a" * 80, WIDE * 40, "공백없이이어지는아주긴한국어문구가계속된다",
         "탭\t과 줄\n바꿈", "\x1b[31m빨강\x1b[0m", EMOJI + " 웃음", "\r되돌림", "  앞뒤 공백  ",
         "e" + chr(0x301) * 5, "보이지" + chr(0x200B) + "않는", "\x00\x07제어",
         "[Request interrupted by user]", "[Request interrupted by user for tool use]"]
TOOLS = ["Bash", "Read", "Edit", "Write", "Grep", "Glob", "Agent", "Task", "WebFetch", "TodoWrite",
         "mcp__google-sheets__get_sheet_data", "mcp__srv__" + "x" * 40, "NotebookEdit", ""]
ARGS = [{}, None, "문자열", [1, 2], {"file_path": "/a/b/" + "c" * 50}, {"description": WIDE * 30},
        {"pattern": 3}, {"command": "ls -al " * 10}, {"file_path": None}, {"description": ""}]


def _stamp(rng, now, ages=None):
    ago = rng.choice(ages or [0, 0.5, 2, 3.9, 4.1, 30, 600, statusline.SULK - 1,
                              statusline.SULK + 5, 86400, -30])
    t = datetime.datetime.fromtimestamp(now - ago, datetime.timezone.utc)
    style = rng.randrange(4)
    if style == 0:
        return t.isoformat()
    if style == 1:
        return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"
    if style == 2:
        return t.strftime("%Y-%m-%dT%H:%M:%SZ")
    return None


IDS = ["a", "b", "c"]
# 실제 기록에서 본 판정에 안 쓰는 줄. 시각이 없거나, 메타이거나, Claude Code 가 넣은 명령 기록이다
MACHINE_LINES = [
    {"type": "permission-mode", "permissionMode": "default"},
    {"type": "file-history-snapshot", "messageId": "m"},
    {"type": "system", "subtype": "local_command", "content": "<command-name>/model</command-name>"},
    {"type": "system", "subtype": "turn_duration"},
    {"type": "attachment", "attachment": {"type": "hook_success"}},
    {"type": "user", "isMeta": True, "message": {"role": "user", "content": "<system-reminder>x</system-reminder>"}},
    {"type": "user", "isMeta": True, "message": {"role": "user", "content": [
        {"type": "text", "text": "Caveat: 로컬 명령"}, {"type": "document", "source": {}}]}},
    {"type": "user", "message": {"role": "user", "content": "<command-name>/usage</command-name>"}},
    {"type": "user", "message": {"role": "user", "content": ""}},
    {"type": "user", "isMeta": True, "message": {"role": "user", "content": [{"type": "text", "text": "사람 말처럼 보이는 메타"}]}},
    {"type": "user", "message": {"role": "user", "content": "<local-command-stdout>ok</local-command-stdout>"}},
    {"type": "user", "isCompactSummary": True, "message": {"role": "user", "content": [
        {"type": "text", "text": "[Request interrupted by user] 뒤에 이어서 한 일 요약"}]}},
]


def _block(rng, uses=True):
    kind = rng.choice(["text", "thinking", "tool_use", "tool_result", "image", "other"] if uses
                      else ["text", "thinking", "tool_result", "image", "other"])
    if kind == "text":
        return {"type": "text", "text": rng.choice(TEXTS)}
    if kind == "thinking":
        return {"type": "thinking", "thinking": "..."}
    if kind == "tool_use":
        return {"type": "tool_use", "id": rng.choice(IDS), "name": rng.choice(TOOLS), "input": rng.choice(ARGS)}
    if kind == "tool_result":
        return {"type": "tool_result", "tool_use_id": rng.choice(IDS), "is_error": rng.choice([True, False, None]),
                "content": rng.choice(["ok", [{"type": "text", "text": "x"}]])}
    if kind == "image":
        return {"type": "image", "source": {"type": "base64", "data": ""}}
    return {"type": "other"}


def _entry(rng, now, ages=None, uses=True):
    if rng.random() < 0.15:
        e = json.loads(json.dumps(rng.choice(MACHINE_LINES)))
        if e["type"] in ("system", "attachment", "user"):
            ts = _stamp(rng, now, ages)
            if ts:
                e["timestamp"] = ts
        return e
    role = rng.choice(["user", "assistant", "user", "assistant", "system", "summary", "attachment"])
    e = {"type": role}
    if role == "assistant" and rng.random() < 0.05:
        e["isApiErrorMessage"] = True
    ts = _stamp(rng, now, ages)
    if ts:
        e["timestamp"] = ts
    if role in ("user", "assistant"):
        if rng.random() < 0.2:
            content = rng.choice(TEXTS)
        else:
            content = [_block(rng, uses) for _ in range(rng.randint(0, 3))]
        e["message"] = {"role": role, "content": content}
    elif rng.random() < 0.3:
        e["message"] = {"content": rng.choice(TEXTS)}
    return e


def _lines(rng, now, ages=None, messy=True, uses=True):
    lines = [json.dumps(_entry(rng, now, ages, uses), ensure_ascii=rng.random() < 0.5)
             for _ in range(rng.randint(0, 12))]
    if messy and rng.random() < 0.2:
        huge = {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "content": "x" * (statusline.TAIL * 2)}]}}
        lines.insert(rng.randint(0, len(lines)), json.dumps(huge))
    if messy and rng.random() < 0.2:
        lines.insert(rng.randint(0, len(lines)), "{깨진 줄")
    return lines


def _write(path, lines, partial="", mtime=None):
    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(l + "\n" for l in lines) + partial)
    if mtime is not None:
        os.utime(path, (mtime, mtime))


def _judge(path):
    name, text, since = statusline.state_of(path)
    assert name in grid.STATES, name
    assert isinstance(text, str), text
    assert since is None or isinstance(since, (int, float)), since
    return name, text


def test_어떤_대화_기록에도_판정이_죽지_않는다():
    now = time.time()
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.jsonl")
        for seed in range(N):
            rng = random.Random(seed)
            lines = _lines(rng, now)
            if lines and rng.random() < 0.3:
                lines[-1] = lines[-1][:rng.randint(1, len(lines[-1]))]
            _write(path, lines)
            try:
                _judge(path)
            except Exception as e:
                raise AssertionError(f"씨앗 {seed}: {type(e).__name__}: {e}\n{lines[-3:]!r}"[:600])


def test_쓰다_만_마지막_줄은_판정을_안_바꾼다():
    """Claude Code 가 줄을 쓰는 도중에도 상태줄은 파일을 읽는다."""
    now = time.time()
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.jsonl")
        for seed in range(N):
            rng = random.Random(seed)
            lines = _lines(rng, now, messy=False)
            _write(path, lines)
            before = _judge(path)
            nxt = json.dumps(_entry(rng, now), ensure_ascii=False)
            _write(path, lines, partial=nxt[:rng.randint(1, len(nxt) - 1)])
            after = _judge(path)
            assert before == after, f"씨앗 {seed}: {before} 가 {after} 로 바뀌었다"


def _say(role, blocks, ago=0.0, now=None, **extra):
    t = datetime.datetime.fromtimestamp((now or time.time()) - ago, datetime.timezone.utc)
    return json.dumps(dict({"type": role, "timestamp": t.isoformat(),
                            "message": {"role": role, "content": blocks}}, **extra), ensure_ascii=False)


def test_마지막_사건이_README_표대로_상태를_정한다():
    """앞에 무엇이 있든 방금 붙은 사건 하나가 상태를 정한다. 앞에는 결과가 안 온 도구 호출을 안 둔다."""
    now = time.time()
    fresh = statusline.FRESH
    read = {"file_path": "/w/보고서.md"}
    cases = [
        ("assistant", [{"type": "tool_use", "id": "z", "name": "Read", "input": read}], 0, ("작업중", "보고서.md 읽는 중")),
        ("assistant", [{"type": "tool_use", "id": "z", "name": "Bash", "input": {"description": "검사"}}], fresh + 10,
         ("승인대기", "검사")),
        ("assistant", [{"type": "tool_use", "id": "z", "name": "Read", "input": read}], fresh + 10, ("작업중", "보고서.md 읽는 중")),
        ("user", [{"type": "tool_result", "is_error": True, "content": "x"}], 0, ("오류", "안 됐어")),
        ("user", [{"type": "tool_result", "content": "x"}], 0, ("생각중", "다음 거 보는 중")),
        ("assistant", [{"type": "thinking", "thinking": "..."}], 0, ("생각중", "생각하는 중")),
        ("assistant", [{"type": "text", "text": "다 했어"}], 0, ("완료", "끝")),
        ("assistant", [{"type": "text", "text": "다 했어"}], fresh + 10, ("숨쉬기", "")),
        ("user", [{"type": "text", "text": "[Request interrupted by user]"}], 0, ("놀람", "앗")),
        ("user", [{"type": "text", "text": "[Request interrupted by user for tool use]"}], 0, ("놀람", "앗")),
        ("user", [{"type": "text", "text": "이거 해줘"}], 0, ("생각중", "무슨 일인지 보는 중")),
        ("user", "이거 해줘", 0, ("생각중", "무슨 일인지 보는 중")),
        ("user", [{"type": "image", "source": {}}, {"type": "text", "text": "이거 봐"}], 0, ("생각중", "무슨 일인지 보는 중")),
        ("user", [{"type": "text", "text": "<system-reminder>x</system-reminder>"},
                  {"type": "text", "text": "진짜 말"}], 0, ("생각중", "무슨 일인지 보는 중")),
    ]
    # 앞 기록 끝을 오래된 답으로 닫는다. 붙인 사건을 못 읽으면 숨쉬기가 나와 앞 기록의 상태와 우연히 겹치지 않는다
    anchor = _say("assistant", [{"type": "text", "text": "지난 답"}], 600, now)
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.jsonl")
        for seed in range(N):
            rng = random.Random(seed)
            base = [l for l in _lines(rng, now, ages=[0, 2, 30, 600], messy=False, uses=False)
                    if '"permission-mode"' not in l]
            role, blocks, ago, want = cases[seed % len(cases)]   # 사례마다 빠짐없이 돈다
            _write(path, base + [anchor, _say(role, blocks, ago, now)])
            got = _judge(path)
            if want[0] == "숨쉬기":
                assert got == want, f"씨앗 {seed}: {role} {blocks!r} {ago}초 전 뒤에 {got}, 기대 {want}"
                continue
            assert got == want, f"씨앗 {seed}: {role} {blocks!r} {ago}초 전 뒤에 {got}, 기대 {want}"


def test_메타_항목과_명령_기록은_상태를_안_바꾼다():
    """슬래시 명령, 시스템이 넣은 메타 항목, 압축 요약, 시각 없는 기록 줄은 사람이나 모델이 한 일이 아니다."""
    now = time.time()
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.jsonl")
        for seed in range(N):
            rng = random.Random(seed)
            base = [l for l in _lines(rng, now, ages=[0, 30, 600], messy=False) if '"permission-mode"' not in l]
            if seed % 2:
                # 앞 기록을 오래된 답으로 닫아 숨쉬기에서 시작한다. 판정 밖 줄을 사람 말로 읽으면 바로 드러난다
                base.append(_say("assistant", [{"type": "text", "text": "지난 답"}], 600, now))
            _write(path, base)
            before = _judge(path)
            # 판정 밖 줄 종류는 씨앗 번호로 빠짐없이 돌고, 그 뒤에 무작위로 더 붙인다
            extra = [dict(MACHINE_LINES[(seed // 2) % len(MACHINE_LINES)])] + \
                [dict(rng.choice(MACHINE_LINES)) for _ in range(rng.randint(0, 2))]
            for x in extra:
                if x["type"] != "permission-mode" and x["type"] != "file-history-snapshot":
                    x["timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            extra = [x for x in extra if x["type"] != "permission-mode"]
            _write(path, base + [json.dumps(x, ensure_ascii=False) for x in extra])
            after = _judge(path)
            assert before == after, f"씨앗 {seed}: {before} 가 {[x.get('type') for x in extra]} 뒤에 {after}"


def test_같이_부른_도구_중_결과가_안_온_것을_보인다():
    now = time.time()
    fresh = statusline.FRESH
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.jsonl")
        for seed in range(N):
            rng = random.Random(seed)
            slow_tool = ["Bash", "Edit", "WebFetch", "Read", "Agent"][seed % 5]
            ago = rng.choice([1, fresh + 30, 300])
            mode = rng.choice([None, "default", "acceptEdits", "auto", "bypassPermissions"])
            uses = [{"type": "tool_use", "id": "p", "name": "Grep", "input": {"pattern": "x"}},
                    {"type": "tool_use", "id": "q", "name": slow_tool, "input": {"file_path": "/w/느린.md"}}]
            if seed % 2:
                uses.reverse()                         # 결과가 온 호출이 뒤에 있어도 안 온 것을 보인다
            lines = [_say("assistant", uses, ago, now),
                     _say("user", [{"type": "tool_result", "tool_use_id": "p", "content": "ok"}], 0, now)]
            if mode:
                lines.insert(0, json.dumps({"type": "permission-mode", "permissionMode": mode}))
            _write(path, lines)
            name, text = _judge(path)
            asks = mode not in ("auto", "bypassPermissions") and slow_tool not in ("Read", "Agent")
            want = "승인대기" if asks and ago > fresh else "작업중"
            assert (name, text) == (want, summary.summarize(slow_tool, {"file_path": "/w/느린.md"})), \
                f"씨앗 {seed}: {slow_tool} {ago}초 {mode} 에서 {name} {text!r}, 기대 {want}"


def test_큰_판정_밖_줄이_창을_밀어도_권한_모드를_읽는다():
    """첨부 한 줄이 판정 창보다 크면 창 앞쪽의 권한 모드 줄이 빠진다. 그래도 허락을 안 묻는 모드를 알아야 한다."""
    now = time.time()
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.jsonl")
        for seed in range(N):
            rng = random.Random(seed)
            mode = ["auto", "bypassPermissions", "default"][seed % 3]
            big = [1, 4, 40, 100][seed % 4] * statusline.TAIL      # 실제 기록에서 본 가장 큰 줄이 3MB 쯤이다
            t = datetime.datetime.fromtimestamp(now, datetime.timezone.utc).isoformat()
            # 첨부 뒤에 판정할 블록을 넉넉히 둬서 첫 창이 거기서 멈추게 한다. 모드 줄은 그 창 밖에 남는다
            talk = [_say("assistant", [{"type": "text", "text": "앞선 말"}], 60, now) for _ in range(statusline.NEED + 1)]
            lines = [json.dumps({"type": "permission-mode", "permissionMode": mode}),
                     json.dumps({"type": "attachment", "timestamp": t, "attachment": {"type": "hook_success",
                                                                                     "content": "x" * big}})] + talk + [
                     _say("assistant", [{"type": "tool_use", "id": "q", "name": "Bash", "input": {}}], 60, now)]
            _write(path, lines)
            got = _judge(path)[0]
            want = "승인대기" if mode == "default" else "작업중"
            assert got == want, f"씨앗 {seed}: {mode} 에서 {big // 1024}KB 첨부 뒤 {got}, 기대 {want}"


def test_끊김_문구를_인용하거나_API_오류로_끝나면():
    now = time.time()
    cases = [
        (_say("user", [{"type": "text", "text": "아까 [Request interrupted by user] 라고 떴어"}], 0, now), "생각중"),
        (_say("user", "요약: [Request interrupted by user for tool use] 이후 이어감", 0, now), "생각중"),
        (_say("assistant", [{"type": "text", "text": "API Error: 529"}], 0, now, isApiErrorMessage=True), "오류"),
    ]
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.jsonl")
        for line, want in cases:
            _write(path, [line])
            assert _judge(path)[0] == want, (line, _judge(path))


def test_오래_조용하면_내용과_상관없이_뾰로통하다():
    now = time.time()
    old = statusline.SULK + 60
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.jsonl")
        for seed in range(N):
            rng = random.Random(seed)
            lines = _lines(rng, now, ages=[old, old + 3600], messy=False)
            _write(path, lines, mtime=now - old)
            assert _judge(path)[0] == "뾰로통", f"씨앗 {seed}"


def _visible(line):
    return bubble.cells(SGR.sub("", line))


def test_상태줄_출력은_늘_크기대로다():
    """어떤 크기, 상태, 문구, 시각에서도 줄 수가 크기 이름대로이고 폭이 창 검사의 계산을 안 넘는다."""
    keep = statusline.SIZE, statusline.BUBBLE, statusline.COLOR
    sizes = grid.sizes()
    try:
        picks = sizes + ["99x99", "", "abc"]
        names = list(grid.STATES) + [None, "없는상태"]
        # 크기와 상태의 짝은 씨앗 번호로 빠짐없이 돈다. 문구와 시각만 무작위다
        for seed in range(max(N * 3, len(picks) * len(names))):
            rng = random.Random(seed)
            size = picks[seed % len(picks)]
            statusline.SIZE = size
            statusline.BUBBLE = rng.random() < 0.8
            statusline.COLOR = rng.random() < 0.5
            statusline._cache.clear()
            used = size if size in sizes else statusline.default_size()
            cw, rows = (int(x) for x in used.split("x"))
            name = names[(seed // len(picks)) % len(names)]
            text = rng.choice(TEXTS) + rng.choice(["", " " + rng.choice(TEXTS)])
            when = rng.uniform(0, 2e9)
            since = rng.choice([None, when, when - rng.uniform(0, 30)])
            art = statusline.panel(name, text, when=when, since=since)
            lines = art.split("\n")
            where = f"씨앗 {seed}: {used} {name} {text!r}"
            assert len(lines) == rows, f"{where}: {len(lines)}줄"
            limit = cw + (1 + bubble.COLS + 4 if statusline.BUBBLE else 0)
            wide = max(_visible(l) for l in lines)
            assert wide <= limit, f"{where}: 폭 {wide} > {limit}"
            bare = SGR.sub("", art)
            ctrl = [hex(ord(c)) for c in bare if ord(c) < 32 and c != "\n" or 0x7F <= ord(c) < 0xA0]
            assert not ctrl, f"{where}: 제어 문자 {ctrl}"
            if not statusline.COLOR:
                assert "\x1b" not in art, where
    finally:
        statusline.SIZE, statusline.BUBBLE, statusline.COLOR = keep
        statusline._cache.clear()


def test_말풍선_상자는_줄마다_폭이_같고_보이는_글자와_무관하다():
    for seed in range(N * 2):
        rng = random.Random(seed)
        text = " ".join(rng.choice(TEXTS) for _ in range(rng.randint(1, 3)))
        text = " ".join(statusline.clean(text).split())
        full = bubble.draw(text)
        widths = {bubble.cells(r) for r in full}
        assert len(widths) == 1, f"씨앗 {seed} {text!r}: 줄 폭 {widths}"
        assert widths.pop() <= bubble.COLS + 4, f"씨앗 {seed} {text!r}"
        for shown in range(0, len(text) + 1, max(1, len(text) // 5)):
            part = bubble.draw(text, shown=shown)
            assert [bubble.cells(r) for r in part] == [bubble.cells(r) for r in full], \
                f"씨앗 {seed} {text!r} shown={shown}"
            seen = "".join("".join(r[2:-2]) for r in part[1:-1]).replace(" ", "")
            assert seen == text[:shown].replace(" ", ""), \
                f"씨앗 {seed} {text!r} shown={shown}: 보이는 글자 {seen!r}"
        kept = "".join("".join(r[2:-2]) for r in full[1:-1]).replace(" ", "")
        assert kept == text.replace(" ", ""), f"씨앗 {seed}: 글자가 빠졌다 {text!r} -> {kept!r}"


def test_도구_요약은_어떤_입력에도_짧은_문구를_낸다():
    for seed in range(N * 2):
        rng = random.Random(seed)
        tool = rng.choice(TOOLS + [None, 3, "Read"])
        arg = rng.choice(ARGS)
        try:
            said = summary.summarize(tool, arg)
        except Exception as e:
            raise AssertionError(f"씨앗 {seed}: {tool!r} {arg!r} 에서 {type(e).__name__}: {e}")
        assert isinstance(said, str), (tool, arg, said)
        if tool not in ("Bash",) and isinstance(tool, str) and tool:
            assert len(said) <= statusline.SAID, f"{tool!r} {arg!r}: {said!r}"


@grid.slow
def test_파이썬마다_판정과_출력_줄_수가_같다():
    """상태줄 명령은 PATH 의 python3 로 돈다. 맥 기본 3.9 에서만 다르게 읽는 형식이 있으면 안 된다."""
    if len(grid.PYTHONS) < 2:
        raise grid.Skip("견줄 파이썬이 하나뿐이다")
    now = time.time()
    code = ("import json, sys; sys.path.insert(0, sys.argv[1]); import statusline\n"
            "print(json.dumps(statusline.state_of(sys.argv[2])[:2], ensure_ascii=False))")
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "t.jsonl")
        for seed in range(grid.times(12)):
            rng = random.Random(seed)
            _write(path, _lines(rng, now))
            seen = {}
            for py in grid.PYTHONS:
                out = subprocess.run([py, "-c", code, PLMI, path], capture_output=True, text=True, timeout=30)
                assert out.returncode == 0, f"씨앗 {seed} {py}: {out.stderr[-300:]}"
                seen[py] = out.stdout.strip()
                size = rng.choice(grid.sizes())
                shown = subprocess.run([py, os.path.join(PLMI, "statusline.py")],
                                       input=json.dumps({"transcript_path": path}),
                                       capture_output=True, text=True, timeout=30,
                                       env=dict(os.environ, PLMI_SIZE=size))
                rows = int(size.split("x")[1])
                assert len(shown.stdout.rstrip("\n").split("\n")) == rows, f"씨앗 {seed} {py} {size}"
                assert shown.stderr == "", f"씨앗 {seed} {py}: {shown.stderr[-300:]}"
            assert len(set(seen.values())) == 1, f"씨앗 {seed}: {seen}"
