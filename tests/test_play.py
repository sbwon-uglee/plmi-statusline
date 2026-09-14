"""창 실행기가 그리는 방식을 가짜 시계로 본다.

실제 시간으로 돌리면 느리고, 컴퓨터가 바쁠 때 장 수가 흔들린다. play 모듈의 시계를 가짜로 바꿔
잠드는 시간을 기록하고 그만큼 시계만 앞으로 민다.
"""
import datetime
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time

import grid

PLMI = os.path.join(grid.ROOT, "plmi")
sys.path.insert(0, PLMI)
import play  # noqa: E402


class Clock:
    def __init__(self):
        self.now = 1_000_000.0
        self.naps = []

    def time(self):
        return self.now

    def sleep(self, secs):
        self.naps.append(secs)
        self.now += secs


def _transcript(d, name, file):
    path = os.path.join(d, name)
    t = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "assistant", "timestamp": t, "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": "u", "name": "Read", "input": {"file_path": f"/w/{file}"}}]}},
            ensure_ascii=False) + "\n")
    return path


def _live(secs, finder, look=None, judge=None):
    """play.live 를 가짜 시계와 가짜 화면으로 돌리고 (화면에 쓴 것, 시계, 찾은 횟수) 를 돌려준다."""
    clock, screen, calls = Clock(), io.StringIO(), []
    keep = play.time, sys.stdout, play.newest_transcript, play.LOOK, play.state_of

    def find():
        calls.append(clock.now)
        return finder(len(calls))

    play.time, sys.stdout, play.newest_transcript = clock, screen, find
    if look is not None:
        play.LOOK = look
    if judge is not None:
        play.state_of = judge
    try:
        play.live(secs)
    finally:
        play.time, sys.stdout, play.newest_transcript, play.LOOK, play.state_of = keep
    return screen.getvalue(), clock, calls


def test_초당_FPS_장을_그리고_커서를_감췄다가_되돌린다():
    with tempfile.TemporaryDirectory() as d:
        path = _transcript(d, "a.jsonl", "보고서.md")
        out, clock, _ = _live(2.0, lambda n: path)
    assert out.startswith("\x1b[?25l"), repr(out[:20])
    assert out.endswith("\x1b[?25h\n"), repr(out[-20:])
    assert set(clock.naps) == {1 / play.FPS}, set(clock.naps)
    assert abs(len(clock.naps) - 2.0 * play.FPS) <= 1, len(clock.naps)


def test_다시_그릴_때는_앞_장의_줄_수만큼_올라간다():
    with tempfile.TemporaryDirectory() as d:
        path = _transcript(d, "a.jsonl", "보고서.md")
        out, _, _ = _live(0.5, lambda n: path)
    body = out[len("\x1b[?25l"):-len("\x1b[?25h\n")]
    rows = len(play.panel("작업중", "x").split("\n"))
    naps = round(0.5 * play.FPS)
    assert not re.match(r"\x1b\[\d+A", body), "첫 장인데 위로 올라갔다"
    ups = re.findall(r"\x1b\[(\d+)A", body)
    assert len(ups) >= naps - 1, f"장 {naps} 개 중 위로 올라간 것이 {len(ups)}번"
    assert set(ups) == {str(rows)}, f"앞 장이 {rows}줄인데 {set(ups)} 줄 올라갔다"
    assert "보고서.md" in out, "대화 기록을 따라가지 않았다"


def test_새_세션이_생기면_LOOK_초_안에_옮겨_간다():
    with tempfile.TemporaryDirectory() as d:
        a = _transcript(d, "a.jsonl", "가.md")
        b = _transcript(d, "b.jsonl", "나.md")
        out, _, calls = _live(1.0, lambda n: a if n < 3 else b, look=0.2)
    assert "가.md" in out and "나.md" in out, "새 세션으로 안 옮겨 갔다"
    assert len(calls) <= 1.0 / 0.2 + 2, f"대화 기록을 {len(calls)}번 찾았다. LOOK 초마다만 찾아야 한다"


def test_판정이_실패하거나_기록이_없어도_그림은_계속_나온다():
    def broken(path):
        raise ValueError("판정 실패")
    with tempfile.TemporaryDirectory() as d:
        path = _transcript(d, "a.jsonl", "보고서.md")
        out, clock, _ = _live(0.3, lambda n: path, judge=broken)
        assert any(0x2800 <= ord(c) <= 0x28FF for c in out), "판정이 실패하니 그림이 안 나왔다"
        out, _, _ = _live(0.3, lambda n: None)
        assert any(0x2800 <= ord(c) <= 0x28FF for c in out), "기록이 없으니 그림이 안 나왔다"


def test_고르는_사이에_지워진_기록은_뒤로_민다():
    with tempfile.TemporaryDirectory() as d:
        real = _transcript(d, "a.jsonl", "보고서.md")
        keep = play.glob.glob
        play.glob.glob = lambda *a, **k: ["/없는/기록.jsonl", real]
        try:
            assert play.newest_transcript() == real
        finally:
            play.glob.glob = keep


def test_초를_안_주면_끝내지_않고_돈다():
    proc = subprocess.Popen([sys.executable, os.path.join(PLMI, "play.py")],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        time.sleep(0.8)
        assert proc.poll() is None, f"초를 안 줬는데 끝났다: {proc.stderr.read()[-300:]}"
    finally:
        proc.terminate()
        proc.wait(timeout=10)
