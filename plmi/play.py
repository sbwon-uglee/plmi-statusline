"""플밍이를 창 하나에서 계속 돌린다. 가장 최근 대화 기록을 따라 상태가 바뀐다.

    python3 plmi/play.py          Ctrl+C 로 끝낸다
    python3 plmi/play.py 10       10초만 돌린다

statusLine 과 달리 12fps 로 스스로 다시 그린다. 한 상태만 보려면 `plmi --preview --state 놀람`.
"""
import glob
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from statusline import panel, state_of

FPS = 12
LOOK = 5.0          # 이 초마다 가장 최근 대화 기록을 다시 골라 새 세션으로 옮겨 간다


def newest_transcript():
    """가장 최근에 쓰인 대화 기록. 어느 워크스페이스의 세션이든 고른다."""
    hits = glob.glob(os.path.join(os.path.expanduser("~/.claude/projects"), "*", "*.jsonl"))

    def mtime(p):
        try:
            return os.path.getmtime(p)
        except OSError:                     # 고르는 사이에 지워진 기록
            return -1.0
    return max(hits, key=mtime) if hits else None


def live(secs=None):
    """상태를 따라가며 계속 돈다. secs 를 주면 그 초 뒤에 끝낸다."""
    end = time.time() + secs if secs else None
    path, checked, rows = newest_transcript(), 0.0, 0
    sys.stdout.write("\x1b[?25l")                      # 커서 감추기
    try:
        while end is None or time.time() < end:
            now = time.time()
            if now - checked > LOOK:
                path, checked = newest_transcript(), now
            try:
                if path:
                    name, text, since = state_of(path)
                    out = panel(name, text, cycle=None, since=since)
                else:
                    out = panel(cycle=None)
            except Exception:
                out = panel(cycle=None)
            n = out.count("\n") + 1
            sys.stdout.write((f"\x1b[{rows}A" if rows else "")
                             + out.replace("\n", "\x1b[K\n") + "\x1b[K\n")
            sys.stdout.flush()
            rows = n
            time.sleep(1 / FPS)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\x1b[?25h\n")               # 커서 되돌리기


def main():
    live(float(sys.argv[1]) if len(sys.argv) > 1 else None)


if __name__ == "__main__":
    main()
