"""Claude Code statusline 용. 지금 상태에 맞는 그림과 말풍선을 찍는다.

    python terminal_char/statusline.py

훅을 쓰지 않는다. Claude Code 가 stdin 으로 넘겨 주는 세션 JSON 에 `transcript_path` 가
들어 있어, 그 파일 끝만 읽어 지금 무슨 일이 벌어지는지 알아낸다. 훅으로 하면 도구 호출마다
프로세스가 끼어들고, UserPromptSubmit 훅은 출력이 그대로 대화에 실려 토큰을 먹는다.
statusline 은 화면에만 찍히므로 대화에 아무것도 남기지 않는다.

트랜스크립트는 수십 MB 까지 자라므로 끝 32KB 만 읽는다.
"""
import glob
import json
import os
import select
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from summary import summarize

HERE = os.path.dirname(os.path.abspath(__file__))
# 손수 구운 크기를 먼저 본다. brew 로 깐 자리는 판을 올릴 때 통째로 갈리므로 거기에
# 두면 사라진다. 홈 아래에 두면 살아남고, 같은 이름이면 손수 구운 것이 이긴다
BAKED = os.path.join(os.path.expanduser("~"), ".claude", "plmi-sizes")
ANIM = os.path.join(HERE, "sprites", "anim")
DIRS = [BAKED, ANIM]
TAIL = 32768                   # 처음 읽어 볼 꼬리 크기
TAIL_MAX = 1 << 21             # 여기까지는 넓혀 가며 다시 읽는다
NEED = 3                       # 판정에 쓸 블록이 이만큼 나올 때까지 넓힌다
FRESH = 4.0                    # 이보다 오래된 마지막 사건은 「방금 일어난 일」로 안 본다
SULK = 900.0                   # 이만큼 아무 일이 없으면 뾰로통해진다
_cache = {}


def sizes():
    """구워 둔 크기. 파일에서 읽으므로 굽는 크기를 늘리면 저절로 늘어난다."""
    out = set()
    for d in DIRS:
        for f in glob.glob(os.path.join(d, "플밍이_*_*.json")):
            out.add(os.path.basename(f).rsplit("_", 1)[1][:-5])
    return sorted(out, key=lambda s: -int(s.split("x")[0]))


def default_size():
    """26칸에 가장 가까운 것. 글자로 박아 두면 굽는 줄 수가 바뀔 때마다 없는 크기가 된다."""
    have = sizes()
    return min(have, key=lambda s: abs(int(s.split("x")[0]) - 26)) if have else ""


SIZE = os.environ.get("PLMI_SIZE") or default_size()


def load(name):
    """크기를 골라 읽는다. 여러 크기를 구워 두고 `PLMI_SIZE` 로 갈아 낀다."""
    if name not in _cache:
        hit = ([p for d in DIRS
                for p in glob.glob(os.path.join(d, f"플밍이_{name}_{SIZE}.json"))]
               or [p for d in DIRS
                   for p in glob.glob(os.path.join(d, f"플밍이_{name}_*.json"))])
        _cache[name] = json.load(open(hit[0], encoding="utf-8")) if hit else None
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


def tail(path):
    """끝에서부터 파싱되는 줄만 골라 시간순으로 돌려준다.

    꼬리 크기를 한 번만 잡으면 안 된다. 도구 결과 한 줄이 창보다 클 때가 있어서
    (실측 66,684바이트 대 32,768바이트) 그런 줄이 끝에 오면 창에 성한 줄이 거의 안 남고,
    판정이 아무것도 못 찾아 숨쉬기로 떨어진다. 일하는 중에 가만히 있는 얼굴이 나온다.
    판정에 쓸 블록이 몇 개 나올 때까지 창을 넓혀 다시 읽는다.
    """
    size = TAIL
    while True:
        out, end = read_tail(path, size)
        if sum(len(blocks(e)) for e in out) >= NEED or size >= TAIL_MAX or size >= end:
            return out
        size *= 4


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
    c = (entry.get("message") or {}).get("content")
    if isinstance(c, list):
        return c
    # 문자열이면 통째로 안 보여 사람이 방금 말을 걸어도 생각중이 안 떴다
    return [{"type": "text", "text": c}] if isinstance(c, str) and c else []


def quiet(path, ev):
    """마지막으로 무슨 일이든 일어난 지 얼마나 됐나.

    항목 종류를 가리지 않고 본다. 도구 결과나 첨부처럼 판정에 안 쓰는 항목도 일이
    일어났다는 증거다. 파일이 자란 시각도 함께 본다.
    """
    ages = [age(e) for e in ev if e.get("timestamp")]
    try:
        ages.append(time.time() - os.path.getmtime(path))
    except OSError:
        pass
    return min(ages) if ages else 0.0


def state_of(path):
    """(상태, 말풍선 문구, 그 일이 일어난 시각). 트랜스크립트 끝을 거꾸로 훑어 마지막 사건을 찾는다.

    시각은 말풍선이 말을 꺼내는 기준이다. 일이 난 그 순간부터 한 글자씩 말한다.
    """
    ev = tail(path)
    # 뾰로통은 「조용하다」는 뜻이라 마지막 사건 전체로 판단한다. 거슬러 올라가 처음 만난
    # text 블록의 나이로 정하면, 도구를 한참 돌리는 중에도 그 앞 답변이 오래됐을 때 일하는
    # 중에 뾰로통이 뜬다.
    q = quiet(path, ev)
    if q > SULK:
        # 조용해진 지 SULK 만큼 지난 순간이 심심해진 순간이다
        return "뾰로통", "심심해", time.time() - q + SULK
    tool = None
    for e in reversed(ev):
        at = stamp(e)
        for b in reversed(blocks(e)):
            kind = b.get("type")
            if kind == "tool_use":
                if tool is None:
                    tool = (b.get("name", ""), b.get("input") or {})
                # 결과가 아직 안 붙었고 시간이 꽤 지났으면 허락을 기다리는 중이다
                waited = age(e) > FRESH
                return ("승인대기" if waited else "작업중"), summarize(*tool), at
            if kind == "tool_result":
                if b.get("is_error"):
                    return "오류", "안 됐어", at
                return "작업중", summarize(*tool) if tool else "다음 거 보는 중", at
            if kind == "thinking":
                return "생각중", "생각하는 중", at
            if kind == "text":
                if e.get("type") == "assistant":
                    return ("완료", "끝", at) if age(e) < FRESH else ("숨쉬기", "", at)
                # 하던 일을 사람이 끊었을 때. Claude Code 가 이 문구를 넣는다
                if "[Request interrupted by user]" in str(b.get("text", "")):
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
    path = ev.get("transcript_path")
    if path and os.path.exists(path):
        try:
            return state_of(path)
        except Exception:
            pass
    from state import read
    return (*read(), None)


def frame(name=None, when=None, fps=None):
    """벽시계로 프레임을 고른다.

    `refreshInterval: 1` 을 켜면 statusline 이 초당 네댓 번 불린다(실측). 호출 횟수를
    세는 대신 시각으로 고르면 부르는 간격이 흔들려도 자세가 시간에 맞게 흘러가고,
    여러 세션이 동시에 불러도 서로 어긋나지 않는다.

    fps 를 낮춰 주면 한 번 그릴 때 더 크게 움직인다. statusline 은 부르는 간격이
    재생기보다 성기므로 낮은 값을 쓴다.
    """
    a = load(name) or load("숨쉬기")
    if not a:
        return ""
    n = len(a["frames"])
    return a["frames"][int((when if when is not None else time.time())
                           * (fps or a["fps"])) % n]


DOTS = 3              # 문구 뒤에서 늘어나는 점의 최대 개수

# 말풍선 박자. 말풍선이 한 번 떠서 그대로 있으면 그림 옆에 붙은 딱지로 보인다.
# 일이 난 순간 문구가 한꺼번에 뜨고, 뒤에서 점이 하나씩 늘고, 쉬었다가 다시 뜬다.
# (점 하나 느는 초, 떠 있는 초, 쉬는 초). 떠 있는 초가 None 이면 안 사라지고,
# 쉬는 초가 None 이면 한 번 떴다가 그친다.
# 점 간격은 상태줄이 불리는 간격보다 짧으면 안 된다. 쉴 때는 초당 한 번 불리므로 0.5초로
# 늘리면 볼 때마다 두 칸씩 건너뛰어 점이 없다가 두 개였다가만 되풀이한다.
TALK = (1.0, 4.0, 3.0)
RHYTHM = {
    # 지금 무슨 일인지 알려 주는 정보라 사라지지 않는다. 일하는 중에는 초당 여섯 번쯤 불린다
    "작업중": (0.5, None, None),
    "생각중": (0.5, None, None),
    # 허락을 기다리는 동안은 일이 멈춰 있어 쉴 때처럼 드물게 불린다
    "승인대기": (1.0, None, None),
    # 한 번 외치는 말이다. 되풀이하면 끊긴 뒤 다음 말을 걸 때까지 계속 앗 앗 한다
    "놀람": (1.0, 4.0, None),
    # 4초만 떠 있는 상태라 쉬는 구간에 걸리면 못 보고 지나간다
    "완료": (1.0, 4.0, None),
}


def speak(at, rhythm=TALK):
    """말을 꺼낸 지 at 초 지났을 때 문구 뒤에 붙일 점 개수. 말풍선이 없는 구간이면 None."""
    beat, hold, rest = rhythm
    if hold is not None:
        if rest is not None:
            at %= hold + rest
        if at >= hold:
            return None
    return int(at / beat) % (DOTS + 1)
# 한 바퀴에 걸리는 초. 프레임 수가 달라도 속도를 맞춘다. 쉴 때는 초당 한 번만 그려지므로
# 1초에 16%씩 돈다. 이웃 자세로만 넘어가야 숨쉬는 것으로 보이고, 크게 건너뛰면 튀어 보인다.
# 3.0 이나 4.0 처럼 프레임 수와 딱 나누어떨어지는 값은 피한다. 같은 자세 서너 개만 반복한다.
CYCLE = 6.3
BUBBLE = os.environ.get("PLMI_BUBBLE", "1") != "0"
COLOR = os.environ.get("PLMI_COLOR", "1") != "0"
CHARS = "0123456789abcdefghijklmnopq"


def tinted(lines, tint, palette, cw, back=None):
    """칸마다 색을 입힌다. 삼각면 무늬는 점을 파내지 않고 색으로만 옮긴다.

    입은 점을 켜서 찍기 때문에 그 칸만 배경색을 같이 준다. 켠 점은 입 색, 안 켠 자리는
    배경색에 깔린 몸 색으로 나온다. 나머지 칸에는 배경을 주지 않는다.

    같은 색이 이어지면 escape 를 다시 안 찍는다. 안 그러면 한 줄에 26번씩 붙어
    출력이 다섯 배로 불어난다. 말풍선 쪽은 손대지 않는다.
    """
    out = []
    rows = back.split("\n") if back else []
    for y, (line, row) in enumerate(zip(lines, tint.split("\n"))):
        bar = rows[y] if y < len(rows) else ""
        buf, prev = [], (None, None)
        for i, chunk in enumerate(line):
            key = row[i] if i < len(row) and i < cw else "."
            bg = bar[i] if i < len(bar) and i < cw else "."
            if (key, bg) != prev:
                buf.append("\x1b[0m")
                if key != ".":
                    buf.append("\x1b[38;2;{};{};{}m".format(*palette[CHARS.index(key)]))
                if bg != ".":
                    buf.append("\x1b[48;2;{};{};{}m".format(*palette[CHARS.index(bg)]))
                prev = (key, bg)
            buf.append(chunk)
        if prev != (".", "."):
            buf.append("\x1b[0m")
        out.append("".join(buf))
    return out


def panel(name=None, text="", when=None, cycle=CYCLE, since=None):
    """그림과 말풍선을 한 장으로 만든다. 말풍선 문구 뒤에는 점을 붙여 돌린다.

    프레임 속도 대신 한 바퀴 도는 시간을 맞춘다. statusline 은 쉴 때 `refreshInterval`
    한계인 초당 한 번만 불리므로, 한 바퀴가 짧아야 그 한 번에 자세가 크게 바뀐다.
    48장짜리를 8fps 로 돌리면 한 번에 6분의 1바퀴라 멈춘 것으로 보인다.

    since 는 그 말을 꺼낸 시각이다. 점이 몇 개인지, 말풍선이 떠 있는지를 여기서 지난 초로
    정한다. statusline 은 부를 때마다 새로 뜨는 프로세스라 앞에서 점을 몇 개 보였는지
    기억할 수 없고, 사건 시각은 대화 기록에 있어 어느 프로세스에서 봐도 같다.
    """
    from bubble import beside, draw
    t = when if when is not None else time.time()
    a = load(name) or load("숨쉬기")
    if not a:
        return ""
    n = len(a["frames"])
    if a.get("hold"):
        rate = 1 / a["hold"]          # 한 장을 정해진 초만큼 붙든다(깜빡임처럼 단발인 것)
    else:
        rate = n / cycle if cycle else a["fps"]
    i = int(t * rate) % n
    art = a["frames"][i]
    if BUBBLE and text:
        said = text.rstrip()
        beat, hold, rest = RHYTHM.get(name, TALK)
        if since is None:
            # 언제 꺼낸 말인지 모르면 벽시계로 맞춘다. 한 번만 할 말도 되풀이해야 보인다
            at, rest = t, TALK[2] if rest is None else rest
        else:
            at = max(0.0, t - since)
        dots = speak(at, (beat, hold, rest))
        if dots is not None:
            # 상자는 점이 다 찼을 때 크기로 잡는다. 점이 늘 때마다 상자가 커지면 그림이 흔들린다
            art = beside(art, draw(said + "." * DOTS, cols=22, shown=len(said) + dots))
    if COLOR and a.get("tints"):
        art = "\n".join(tinted(art.split("\n"), a["tints"][i], a["palette"], a["cw"],
                                (a.get("backs") or [None] * n)[i]))
    return art


def emit(text):
    """받는 쪽이 먼저 닫아도 조용히 끝낸다. statusline 이 에러를 뱉으면 화면에 뜬다."""
    try:
        sys.stdout.write(text + "\n")
        sys.stdout.flush()
    except BrokenPipeError:
        try:
            os.close(sys.stdout.fileno())
        except Exception:
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
