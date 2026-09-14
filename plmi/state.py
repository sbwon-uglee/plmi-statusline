"""상태를 손으로 지정해 둔다. 시연이나 시험용이다.

    python3 plmi/state.py 작업중 "시트 여는 중"
    python3 plmi/state.py 완료 --hold 1.5

statusline 은 평소 대화 기록에서 상태를 알아내고, 기록을 못 읽을 때만 이 파일을 본다.
hold 를 주면 그 시간이 지난 뒤 저절로 숨쉬기로 돌아간다.
"""
import json
import os
import sys
import tempfile
import time

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sprites", "state.json")
REST = "숨쉬기"


def write(name, text, hold):
    # 부를 때마다 다른 임시 파일에 써서 두 번 동시에 불러도 서로의 임시 파일을 안 옮긴다
    fd, tmp = tempfile.mkstemp(prefix=".state-", dir=os.path.dirname(PATH))
    with os.fdopen(fd, "w", encoding="utf-8") as f:
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
    return s.get("state") or REST, s.get("text", "")


if __name__ == "__main__":
    args = sys.argv[1:]
    hold = 0.0
    if "--hold" in args:
        i = args.index("--hold")
        hold = float(args[i + 1])
        del args[i:i + 2]
    write(args[0] if args else REST, args[1] if len(args) > 1 else "", hold)
