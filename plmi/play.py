"""플밍이를 터미널에서 돌린다.

    python terminal_char/play.py --live           지금 대화 기록을 따라 계속 돈다 (Ctrl+C 로 끝)
    python terminal_char/play.py [애니이름] [초]    한 상태만 돌려 본다

`--live` 가 본체다. Claude Code statusline 은 한 턴에 한 번쯤만 다시 불려서(실측 14초에
1회) 애니메이션이 안 된다. 창을 하나 더 띄워 여기에 두면 계속 움직인다.
"""
import glob
import json
import os
import sys
import time

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sprites", "anim")


def newest_transcript():
    """이 워크스페이스에서 가장 최근에 쓰인 대화 기록을 고른다."""
    root = os.path.expanduser("~/.claude/projects")
    cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    key = cwd.replace("/", "-")
    hits = glob.glob(os.path.join(root, key, "*.jsonl"))
    return max(hits, key=os.path.getmtime) if hits else None


def live(secs=None, fps=12):
    """상태를 따라가며 계속 돈다. 대화 기록은 몇 초마다 다시 찾는다(새 세션 대비)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from statusline import panel, state_of
    end = time.time() + secs if secs else None
    path, checked, rows = newest_transcript(), 0.0, 0
    sys.stdout.write("\x1b[?25l")                      # 커서 감추기
    try:
        while end is None or time.time() < end:
            now = time.time()
            if now - checked > 5:
                path, checked = newest_transcript(), now
            try:
                out = panel(*state_of(path), cycle=None) if path else panel(cycle=None)
            except Exception:
                out = panel(cycle=None)
            n = out.count("\n") + 1
            sys.stdout.write((f"\x1b[{rows}A" if rows else "")
                             + out.replace("\n", "\x1b[K\n") + "\x1b[K\n")
            sys.stdout.flush()
            rows = n
            time.sleep(1 / fps)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\x1b[?25h\n")               # 커서 되돌리기


def main():
    if "--live" in sys.argv:
        rest = [a for a in sys.argv[2:] if not a.startswith("--")]
        live(float(rest[0]) if rest else None)
        return
    name = sys.argv[1] if len(sys.argv) > 1 else "숨쉬기"
    secs = float(sys.argv[2]) if len(sys.argv) > 2 else 4.0
    hit = glob.glob(os.path.join(OUT, f"*{name}*.json"))
    if not hit:
        print("없는 이름. 있는 것:", ", ".join(sorted(
            os.path.basename(p) for p in glob.glob(os.path.join(OUT, "*.json")))))
        return
    a = json.load(open(hit[0], encoding="utf-8"))
    frames, fps = a["frames"], a["fps"]
    end = time.time() + secs
    print("\n" * a["ch"], end="")
    while time.time() < end:
        f = frames[int(time.time() * fps) % len(frames)]
        sys.stdout.write(f"\x1b[{a['ch']}A" + f.replace("\n", "\x1b[K\n") + "\x1b[K\n")
        sys.stdout.flush()
        time.sleep(1 / fps)


if __name__ == "__main__":
    main()
