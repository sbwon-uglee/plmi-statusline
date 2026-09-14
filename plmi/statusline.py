"""Claude Code statusline 용. 지금 상태에 맞는 그림과 말풍선을 찍는다.

    python3 plmi/statusline.py                 stdin 의 세션 JSON 으로 상태를 정해 찍는다
    python3 plmi/statusline.py 작업중 "문구"     그 상태로 한 장 찍는다

세션 JSON 의 `transcript_path` 끝을 읽어 상태를 정한다. 대화 기록은 수백 MB 까지 자라므로
끝 32KB 부터 읽고, 모자라면 8MB 까지 넓힌다.
"""
import glob
import json
import os
import re
import select
import sys
import time
import unicodedata
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from bubble import beside, draw
from summary import summarize

# `plmi --bake` 로 구운 크기. 판을 올려도 남도록 홈 아래에 두고, 같은 이름이면 이쪽을 먼저 쓴다
BAKED = os.path.join(os.path.expanduser("~"), ".claude", "plmi-sizes")
ANIM = os.path.join(HERE, "sprites", "anim")
DIRS = [BAKED, ANIM]
TAIL = 32768                   # 처음 읽어 볼 꼬리 크기
TAIL_MAX = 1 << 23             # 여기까지는 넓혀 가며 다시 읽는다. 도구 결과 한 줄이 3MB 를 넘기도 한다
NEED = 3                       # 판정에 쓸 블록이 이만큼 나올 때까지 넓힌다
FRESH = 4.0                    # 이보다 오래된 마지막 사건은 「방금 일어난 일」로 안 본다
SULK = 900.0                   # 이만큼 아무 일이 없으면 뾰로통해진다
JUDGED = ("tool_use", "tool_result", "thinking", "text")   # 상태를 정하는 블록
# Claude Code 가 user 자리에 넣는 기록의 글머리. 판정에서 뺀다
MACHINE = ("<command-name>", "<command-message>", "<command-args>", "<local-command-stdout>",
           "<local-command-stderr>", "<local-command-caveat>", "<system-reminder>", "Caveat:")
INTERRUPT = "[Request interrupted by user"   # 사람이 끊으면 넣는 문구. 도구 도중이면 뒤에 for tool use 가 붙는다
# 허락을 묻지 않는 권한 모드와 도구. 이때는 결과가 늦어도 허락을 기다리는 것이 아니다
NO_ASK_MODES = ("auto", "bypassPermissions")
NO_ASK_TOOLS = ("Read", "Glob", "Grep", "LS", "NotebookRead", "TodoWrite", "Task", "Agent")
CYCLE = 6.3                    # hold 가 없는 상태가 한 바퀴 도는 초. 프레임 수를 이 값으로 나눈 것이 정수면 1초마다 볼 때 몇 자세만 되풀이한다
BUBBLE = os.environ.get("PLMI_BUBBLE", "1") != "0"
COLOR = os.environ.get("PLMI_COLOR", "1") != "0"
CHARS = "0123456789abcdefghijklmn"   # 색 칸 문자. 팔레트 순서다
DOTS = 3                       # 문구 뒤에서 늘어나는 점의 최대 개수
SAID = 22                      # 말풍선 문구의 최대 글자 수. 이 안이면 가장 작은 16x8 에서도 말풍선이 그림보다 높아지지 않는다

# 말풍선 박자. (점 하나 느는 초, 떠 있는 초, 쉬는 초)
# 떠 있는 초가 None 이면 안 사라지고, 쉬는 초가 None 이면 한 번만 뜬다.
# 점 간격이 상태줄이 불리는 간격(쉴 때 1초)보다 짧으면 점이 건너뛰어 보인다.
TALK = (1.0, 4.0, 3.0)
RHYTHM = {
    # 지금 하는 일이라 사라지지 않는다
    "작업중": (0.5, None, None),
    "생각중": (0.5, None, None),
    # 허락을 기다리는 동안은 드물게 불릴 수 있어 쉴 때 간격을 쓴다
    "승인대기": (1.0, None, None),
    # 한 번만 뜬다. 놀람은 사람이 다음 말을 걸 때까지 이어진다
    "놀람": (1.0, 4.0, None),
    "완료": (1.0, 4.0, None),
}
_cache = {}


def sizes():
    """구워 둔 크기를 칸 수가 큰 것부터. 두 폴더의 파일 이름에서 모은다."""
    out = set()
    for d in DIRS:
        for f in glob.glob(os.path.join(glob.escape(d), "플밍이_*_*.json")):
            out.add(os.path.basename(f).rsplit("_", 1)[1][:-5])
    return sorted(out, key=lambda s: (-int(s.split("x")[0]), s))


def default_size():
    """구워 둔 크기 중 26칸에 가장 가까운 것. 칸 수가 같으면 이름 순서로 앞의 것. 없으면 빈 문자열."""
    have = sizes()
    return min(have, key=lambda s: (abs(int(s.split("x")[0]) - 26), s)) if have else ""


SIZE = os.environ.get("PLMI_SIZE") or default_size()


def load(name):
    """`플밍이_<name>_<SIZE>.json` 을 읽는다. 그 크기가 없으면 26칸에 가장 가까운 구운 크기를 쓴다.

    상태마다 다른 크기를 집으면 상태가 바뀔 때 상태줄 줄 수가 달라진다. 구운 폴더의 파일이
    깨졌으면 저장소 쪽 같은 이름을 쓴다.
    """
    if name not in _cache:
        _cache[name] = None
        for size in (SIZE, default_size()):
            for d in DIRS:
                try:
                    with open(os.path.join(d, f"플밍이_{name}_{size}.json"), encoding="utf-8") as f:
                        a = json.load(f)
                    if a.get("frames"):
                        _cache[name] = a
                        return a
                except (OSError, ValueError, AttributeError):
                    continue
    return _cache[name]


def read_tail(path, size):
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        end = f.tell()
        f.seek(max(0, end - size))
        raw = f.read().decode("utf-8", "ignore")
    out = []
    for line in raw.split("\n"):
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out, end


def tail(path, enough=None):
    """파일 끝 창에서 JSON 으로 읽히는 줄을 파일 순서대로 돌려준다.

    도구 결과나 첨부 한 줄이 창보다 클 수 있어서, enough 가 참이 될 때까지 창을 네 배씩 넓혀
    TAIL_MAX 까지 다시 읽는다. enough 를 안 주면 판정에 쓸 블록이 NEED 개 나올 때까지다.
    """
    enough = enough or (lambda out: sum(1 for e in out for b in judged(e)) >= NEED)
    size = TAIL
    while True:
        out, end = read_tail(path, size)
        if enough(out) or size >= TAIL_MAX or size >= end:
            return out
        size *= 4


def mode_in(ev):
    """가장 최근 권한 모드. 권한 모드 줄과 사람 말 항목에 적힌다. 없으면 None."""
    return next((e["permissionMode"] for e in reversed(ev) if isinstance(e.get("permissionMode"), str)), None)


def stamp(entry):
    """항목이 쓰인 시각(초). 없거나 못 읽으면 None."""
    ts = entry.get("timestamp")
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def age(entry):
    at = stamp(entry)
    return time.time() - at if at is not None else 0.0


def blocks(entry):
    """그 항목이 담은 내용 블록. 사람 말은 문자열로 오기도 한다."""
    msg = entry.get("message")
    c = msg.get("content") if isinstance(msg, dict) else None
    if isinstance(c, list):
        return [b for b in c if isinstance(b, dict)]
    return [{"type": "text", "text": c}] if isinstance(c, str) and c else []


def judged(entry):
    """상태를 정하는 블록만. 메타 항목, 압축 요약, Claude Code 가 넣은 명령 기록은 뺀다."""
    if entry.get("isMeta") or entry.get("isCompactSummary"):
        return []
    out = []
    for b in blocks(entry):
        if b.get("type") not in JUDGED:
            continue
        if entry.get("type") == "user" and b.get("type") == "text" \
                and str(b.get("text", "")).lstrip().startswith(MACHINE):
            continue
        out.append(b)
    return out


def quiet(path, ev):
    """마지막으로 무슨 일이든 일어난 지 얼마나 됐나.

    항목 종류를 가리지 않고 본다. 첨부처럼 판정에 안 쓰는 항목도 센다. 파일이 자란 시각도
    함께 본다.
    """
    ages = [age(e) for e in ev if e.get("timestamp")]
    try:
        ages.append(time.time() - os.path.getmtime(path))
    except OSError:
        pass
    return min(ages) if ages else 0.0


def state_of(path):
    """(상태, 말풍선 문구, 그 일이 일어난 시각). 대화 기록 끝을 거꾸로 훑어 마지막 사건을 찾는다.

    시각은 말풍선 박자의 기준이다. 일이 난 그 순간 문구가 뜨고 점이 없는 데서부터 는다.
    """
    ev = tail(path)
    # 뾰로통은 블록 종류와 상관없이 마지막 기록 시각과 파일 수정 시각으로 정한다
    q = quiet(path, ev)
    if q > SULK:
        # 조용해진 지 SULK 만큼 지난 순간이 심심해진 순간이다
        return "뾰로통", "심심해", time.time() - q + SULK
    answered = {b.get("tool_use_id") for e in ev for b in blocks(e) if b.get("type") == "tool_result"}

    def running(e, b):
        """결과가 아직 안 온 도구 호출. 허락을 묻는 도구가 FRESH 초 넘게 결과가 없으면 허락을 기다리는 것이다.

        권한 모드 줄은 판정 창 밖에 있을 수 있다. 허락을 기다리는지 가를 때만 창을 넓혀 찾는다.
        """
        waited = b.get("name") not in NO_ASK_TOOLS and age(e) > FRESH
        if waited:
            mode = mode_in(ev) or mode_in(tail(path, mode_in))
            waited = mode not in NO_ASK_MODES
        return ("승인대기" if waited else "작업중"), summarize(b.get("name", ""), b.get("input")), stamp(e)

    for e in reversed(ev):
        at = stamp(e)
        if e.get("type") == "assistant" and e.get("isApiErrorMessage"):
            return "오류", "안 됐어", at
        for b in reversed(judged(e)):
            kind = b.get("type")
            if kind == "tool_use":
                return running(e, b)
            if kind == "tool_result":
                if b.get("is_error"):
                    return "오류", "안 됐어", at
                # 같이 부른 다른 도구가 아직 돌면 그 도구를 보인다
                for e2 in reversed(ev):
                    for b2 in reversed(blocks(e2)):
                        if b2.get("type") == "tool_use" and b2.get("id") not in answered:
                            return running(e2, b2)
                # 결과를 받은 모델이 다음 할 일을 정하는 중이다
                return "생각중", "다음 거 보는 중", at
            if kind == "thinking":
                return "생각중", "생각하는 중", at
            if kind == "text":
                if e.get("type") == "assistant":
                    return ("완료", "끝", at) if age(e) < FRESH else ("숨쉬기", "", at)
                if str(b.get("text", "")).lstrip().startswith(INTERRUPT):
                    return "놀람", "앗", at
                return "생각중", "무슨 일인지 보는 중", at
    return "숨쉬기", "", None


def read_state():
    """statusline 이 받은 세션 JSON 에서 상태를 뽑는다. 없으면 손으로 적어 둔 것을 쓴다."""
    ev = {}
    if not sys.stdin.isatty() and select.select([sys.stdin], [], [], 0.05)[0]:
        try:
            ev = json.loads(sys.stdin.read() or "{}")
        except Exception:
            ev = {}
    path = ev.get("transcript_path") if isinstance(ev, dict) else None
    if path and os.path.exists(path):
        try:
            return state_of(path)
        except Exception:
            pass
    from state import read
    return (*read(), None)


def frame(name=None):
    """색과 말풍선 없이 벽시계로 고른 한 장. panel 이 실패했을 때와 bubble.py 시연에 쓴다."""
    a = load(name) or load("숨쉬기")
    if not a:
        return ""
    return a["frames"][int(time.time() * a["fps"]) % len(a["frames"])]


ESCAPE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def clean(text):
    """말풍선에 찍을 수 있는 글자만 남긴다. escape 와 제어 문자는 칸 수를 흔들어 상자를 깨뜨린다."""
    text = ESCAPE.sub("", str(text))
    return "".join(" " if unicodedata.category(c)[0] == "C" else c for c in text)


def speak(at, rhythm):
    """말을 꺼낸 지 at 초 지났을 때 문구 뒤에 붙일 점 개수. 말풍선이 없는 구간이면 None."""
    beat, stay, rest = rhythm
    if stay is not None:
        if rest is not None:
            at %= stay + rest
        if at >= stay:
            return None
    return int(at / beat) % (DOTS + 1)


def tinted(lines, tint, palette, cw):
    """칸마다 앞색을 입힌다. 같은 색이 이어지면 escape 를 다시 찍지 않는다.

    cw 칸 너머의 말풍선은 칠하지 않는다.
    """
    out = []
    for line, row in zip(lines, tint.split("\n")):
        buf, prev = [], None
        for i, chunk in enumerate(line):
            key = row[i] if i < len(row) and i < cw else "."
            if key != prev:
                buf.append("\x1b[0m")
                if key != ".":
                    buf.append("\x1b[38;2;{};{};{}m".format(*palette[CHARS.index(key)]))
                prev = key
            buf.append(chunk)
        if prev != ".":
            buf.append("\x1b[0m")
        out.append("".join(buf))
    return out


def panel(name=None, text="", when=None, cycle=CYCLE, since=None):
    """그림과 말풍선을 한 장으로 만든다. 말풍선 문구 뒤에는 점을 붙여 돌린다.

    when 은 그릴 시각이고 비우면 지금이다. 스프라이트에 hold 가 있으면 한 장을 그 초만큼
    보이고, 없으면 cycle 초에 한 바퀴 돈다. cycle 이 None 이면 스프라이트의 fps 를 쓴다.

    since 는 그 말을 꺼낸 시각이다. 점 개수와 말풍선을 띄울지를 여기서 지난 초로 정하고,
    None 이면 벽시계로 맞춘다.
    """
    t = when if when is not None else time.time()
    a = load(name) or load("숨쉬기")
    if not a:
        return ""
    n = len(a["frames"])
    if a.get("hold"):
        rate = 1 / a["hold"]          # 한 장을 hold 초만큼 보인다
    else:
        rate = n / cycle if cycle else a["fps"]
    i = int(t * rate) % n
    art = a["frames"][i]
    if BUBBLE and text:
        said = " ".join(clean(text).split())[:SAID]
        beat, stay, rest = RHYTHM.get(name, TALK)
        if since is None:
            # 언제 꺼낸 말인지 모르면 벽시계로 맞춘다. 한 번만 할 말도 되풀이해야 보인다
            at, rest = t, TALK[2] if rest is None else rest
        else:
            at = max(0.0, t - since)
        dots = speak(at, (beat, stay, rest))
        if dots is not None:
            # 상자는 점이 다 찼을 때 크기로 잡는다. 점이 늘 때마다 상자가 커지면 그림이 흔들린다
            art = beside(art, draw(said + "." * DOTS, shown=len(said) + dots))
    if COLOR and a.get("tints"):
        art = "\n".join(tinted(art.split("\n"), a["tints"][i], a["palette"], a["cw"]))
    return art


def emit(text):
    """UTF-8 로 찍는다. 받는 쪽이 먼저 닫아도 BrokenPipeError 없이 끝낸다.

    로캘이 UTF-8 이 아니면 파이썬이 브라유 점을 못 찍고 죽어 상태줄이 빈다. 바이트로 바로 쓴다.
    """
    try:
        sys.stdout.buffer.write((text + "\n").encode("utf-8"))
        sys.stdout.flush()
    except BrokenPipeError:
        # 닫으면 종료할 때 남은 버퍼를 비우다 다시 오류를 찍는다. /dev/null 로 돌려 조용히 버린다
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except OSError:
            pass


if __name__ == "__main__":
    if len(sys.argv) > 1:
        emit(panel(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ""))
    else:
        try:
            name, text, since = read_state()
            emit(panel(name, text, since=since))
        except Exception:
            emit(frame("숨쉬기"))
