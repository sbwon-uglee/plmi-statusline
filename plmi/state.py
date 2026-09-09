"""상태를 손으로 지정해 둔다. 시연이나 시험용이다.

    python terminal_char/state.py 작업중 "시트 여는 중"
    python terminal_char/state.py 완료 --hold 1.5

statusline 은 평소 대화 기록에서 상태를 알아내고, 기록을 못 읽을 때만 이 파일을 본다.
hold 를 주면 그 시간이 지난 뒤 저절로 숨쉬기로 돌아간다.
"""
import json
import os
import sys
import time

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sprites", "state.json")
REST = "숨쉬기"


def write(name, hold=0.0, text=""):
    tmp = PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"state": name, "text": text,
                   "until": time.time() + hold if hold else 0}, f, ensure_ascii=False)
    os.replace(tmp, PATH)          # 갈아치우기라 statusline 이 반쯤 쓰인 파일을 볼 일이 없다


def read():
    """(상태, 말풍선 문구). 시간이 지난 상태는 저절로 숨쉬기로 돌아간다."""
    try:
        with open(PATH, encoding="utf-8") as f:
            s = json.load(f)
    except Exception:
        return REST, ""
    if s.get("until") and time.time() > s["until"]:
        return REST, ""
    return s.get("state", REST), s.get("text", "")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    hold = 0.0
    if "--hold" in sys.argv:
        hold = float(sys.argv[sys.argv.index("--hold") + 1])
    write(args[0] if args else REST, hold, args[1] if len(args) > 1 else "")
