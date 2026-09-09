"""플밍이를 Claude Code statusLine 에 붙이거나 뗀다.

    python3 plmi/install.py                 사용자 설정에 붙인다
    python3 plmi/install.py --size 36x15    큰 그림으로
    python3 plmi/install.py --scope project 지금 폴더의 .claude 에만
    python3 plmi/install.py --uninstall     뗀다
    python3 plmi/install.py --dry-run       쓸 내용만 보여 준다

statusLine 은 플러그인으로 실을 수 없다. 플러그인 루트의 settings.json 이 받는 키는
agent 와 subagentStatusLine 뿐이라, 사용자나 프로젝트 settings.json 을 직접 고쳐야 한다.

경로는 절대경로로 쓴다. statusline.py 가 스프라이트를 자기 파일 기준으로 찾으므로
어느 폴더에서 Claude Code 를 띄우든 그대로 돈다.
"""
import argparse
import datetime
import glob
import json
import os
import re
import shutil
import sys

CELLAR = re.compile(r"(?P<prefix>.*)/Cellar/(?P<name>[^/]+)/[^/]+/(?P<rest>.*)")


def stable(path):
    """설정에 적어도 버전이 올라가면서 깨지지 않을 경로로 바꾼다.

    brew 는 파일을 `<prefix>/Cellar/<이름>/<버전>/` 에 두고 `<prefix>/opt/<이름>` 이
    지금 버전을 가리키게 한다. Cellar 쪽을 settings.json 에 적으면 다음 `brew upgrade`
    가 그 폴더를 지워 상태줄이 아무 말 없이 죽는다. opt 쪽은 링크가 옮겨갈 뿐이라 산다.

    brew 로 깐 것이 아니면 실제 경로를 그대로 쓴다. `bin/plmi` 처럼 심볼릭 링크로 부를
    수 있으므로 realpath 로 한 번 편 뒤에 본다.
    """
    real = os.path.realpath(path)
    m = CELLAR.match(real)
    if not m:
        return real
    opt = os.path.join(m.group("prefix"), "opt", m.group("name"), m.group("rest"))
    return opt if os.path.exists(opt) else real


HERE = os.path.dirname(stable(__file__))
RUNNER = os.path.join(HERE, "statusline.py")
SIZES = sorted({os.path.basename(f).rsplit("_", 1)[1][:-5]
                for f in glob.glob(os.path.join(HERE, "sprites", "anim", "*.json"))},
               key=lambda s: -int(s.split("x")[0]))
# 줄 수는 굽고 나서 정해지므로 기본 크기를 글자로 박아 두면 그때마다 없는 크기가 된다.
# 26칸에 가장 가까운 것을 고른다
DEFAULT_SIZE = min(SIZES, key=lambda s: abs(int(s.split("x")[0]) - 26)) if SIZES else ""


def version():
    try:
        with open(os.path.join(os.path.dirname(HERE), "VERSION"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "0.0.0"


def settings_path(scope):
    root = os.path.expanduser("~") if scope == "user" else os.getcwd()
    return os.path.join(root, ".claude", "settings.json")


def load(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        text = f.read().strip()
    return json.loads(text) if text else {}


def save(path, data):
    """쓰기 전에 백업한다. 사람이 손으로 만든 설정이 들어 있는 파일이다."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        backup = f"{path}.bak_{stamp}_plmi"
        shutil.copy2(path, backup)
        print(f"  백업 {backup}")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def command(size):
    """PATH 의 python3 를 쓴다. sys.executable 을 박으면 그때 그 파이썬을 지우거나
    버전을 올렸을 때 statusLine 이 조용히 죽는다. 런타임은 표준 라이브러리만 쓰므로
    어느 python3 에서나 돈다."""
    return f"PLMI_SIZE={size} python3 {RUNNER}"


def mine(entry):
    """이 저장소가 넣은 statusLine 인지 본다. 남의 것을 말없이 덮지 않으려는 것이다."""
    return isinstance(entry, dict) and RUNNER in str(entry.get("command", ""))


def main():
    ap = argparse.ArgumentParser(description="플밍이 statusLine 설치")
    ap.add_argument("--version", action="version", version=version())
    ap.add_argument("--size", default=DEFAULT_SIZE, choices=SIZES,
                    help=f"그림 크기. 있는 것 = {', '.join(SIZES)}")
    ap.add_argument("--scope", default="user", choices=("user", "project"),
                    help="user 는 ~/.claude, project 는 지금 폴더의 .claude")
    ap.add_argument("--uninstall", action="store_true", help="statusLine 을 뗀다")
    ap.add_argument("--force", action="store_true", help="다른 statusLine 이 있어도 덮는다")
    ap.add_argument("--dry-run", action="store_true", help="쓰지 않고 보여만 준다")
    a = ap.parse_args()

    if not os.path.exists(RUNNER):
        sys.exit(f"statusline.py 를 못 찾았다: {RUNNER}")
    if not SIZES:
        sys.exit("스프라이트가 없다. plmi/sprites/anim 을 확인할 것")

    path = settings_path(a.scope)
    data = load(path)
    now = data.get("statusLine")

    if a.uninstall:
        if not now:
            print("붙어 있는 statusLine 이 없다")
            return
        if not mine(now) and not a.force:
            sys.exit(f"플밍이가 아닌 statusLine 이 있다. 그대로 둔다\n  {now.get('command')}")
        data.pop("statusLine", None)
        print(f"뗀다: {path}")
        if not a.dry_run:
            save(path, data)
        return

    if now and not mine(now) and not a.force:
        sys.exit("이미 다른 statusLine 이 있다. 덮으려면 --force\n"
                 f"  지금: {now.get('command')}\n"
                 f"  넣으려던 것: {command(a.size)}")

    data["statusLine"] = {"type": "command", "command": command(a.size),
                          "refreshInterval": 1}
    print(f"설정 파일 {path}")
    print("  " + json.dumps(data["statusLine"], ensure_ascii=False))
    if a.dry_run:
        print("  (--dry-run 이라 쓰지 않았다)")
        return
    save(path, data)
    print("붙였다. Claude Code 를 다시 띄우면 플밍이가 나온다")


if __name__ == "__main__":
    main()
