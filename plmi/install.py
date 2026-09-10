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
import subprocess
import sys
import time

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
# 손수 구운 크기를 두는 자리. brew 로 깐 자리는 읽기 전용이고 판을 올릴 때 갈린다
BAKED = os.path.join(os.path.expanduser("~"), ".claude", "plmi-sizes")
SIZES = sorted({os.path.basename(f).rsplit("_", 1)[1][:-5]
                for d in (BAKED, os.path.join(HERE, "sprites", "anim"))
                for f in glob.glob(os.path.join(d, "플밍이_*_*.json"))},
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


def bake(cols):
    """그 칸 수로 스프라이트를 구워 홈 아래에 둔다.

    줄 수는 굽고 나서 정해지므로 칸 수만 받는다. 굽는 쪽은 numpy 와 pillow 가 필요해서
    상태줄 쪽과 갈라 두었다. `uv` 가 있으면 그때만 받아 쓰고, 없으면 이미 깔린 것을 쓴다.
    """
    anim = os.path.join(HERE, "anim.py")
    art = os.path.join(os.path.dirname(HERE), "assets")
    if not os.path.exists(anim) or not os.path.isdir(art):
        sys.exit("굽는 데 필요한 파일이 없다. 저장소를 클론해 쓰거나 새 판으로 올려라")
    if shutil.which("uv"):
        cmd = ["uv", "run", "--quiet", "--with", "numpy", "--with", "pillow",
               "python", anim]
    else:
        probe = subprocess.run(["python3", "-c", "import numpy, PIL"],
                               capture_output=True)
        if probe.returncode != 0:
            sys.exit("numpy 와 pillow 가 필요하다. uv 를 깔거나 pip install numpy pillow")
        cmd = ["python3", anim]
    out = subprocess.run(cmd + ["--cols", str(cols), "--out", BAKED])
    if out.returncode != 0:
        sys.exit("굽다가 멈췄다")
    made = sorted(glob.glob(os.path.join(BAKED, f"플밍이_*_{cols}x*.json")))
    if not made:
        sys.exit("구워진 것이 없다")
    size = os.path.basename(made[0]).rsplit("_", 1)[1][:-5]
    print(f"구웠다. {size} 로 붙이려면 plmi --size {size}")
    return 0


def preview(size, secs, state):
    """붙이기 전에 그 크기로 몇 초 돌려 보여 준다.

    전에는 붙이고 Claude Code 를 다시 띄워야 처음 봤다. 크기가 마음에 안 들면 붙이고,
    다시 띄우고, 다시 붙이는 왕복을 해야 했다.

    상태줄을 그리는 그 코드를 그대로 부른다. 따로 그리면 실제와 다른 것을 보여 주게 된다.
    """
    os.environ["PLMI_SIZE"] = size
    sys.path.insert(0, HERE)
    import statusline

    art = statusline.panel(state, "", when=0.0)
    rows = len(art.split("\n"))
    print(f"{size}, {state}, {secs:g}초. Ctrl+C 로 끝")
    print("\n" * rows, end="")
    end = time.time() + secs
    try:
        while time.time() < end:
            art = statusline.panel(state, "")
            sys.stdout.write(f"\x1b[{rows}A"
                             + art.replace("\n", "\x1b[K\n") + "\x1b[K\n")
            sys.stdout.flush()
            time.sleep(0.08)
    except KeyboardInterrupt:
        pass
    return 0


def fits(size):
    """지금 창에 들어가는 크기인지. 창보다 넓으면 줄바꿈으로 그림이 무너진다."""
    cols, rows = shutil.get_terminal_size((80, 24))
    w, h = (int(x) for x in size.split("x"))
    return w <= cols and h < rows


def settings_path(scope, where=None):
    """붙일 settings.json 자리.

    `user` 는 홈, `project` 는 워크스페이스 폴더다. 워크스페이스는 `where` 로 지목한다.
    비우면 지금 폴더다. 지목할 길이 없으면 붙이려는 워크스페이스마다 그 폴더로 옮겨
    가야 하고, 어디에 붙였는지도 셸 이력에만 남는다.
    """
    if scope == "user":
        return os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
    root = os.path.abspath(os.path.expanduser(where or os.getcwd()))
    return os.path.join(root, ".claude", "settings.json")


def installed_at():
    """플밍이가 붙어 있는 settings.json 을 찾는다.

    떼려면 어디에 붙였는지 알아야 하는데, 프로젝트 스코프로 여러 워크스페이스에 붙이면
    사람이 그것을 기억하고 있어야 했다.
    """
    seen, out = set(), []
    home = os.path.expanduser("~")
    roots = [home]
    # 워크스페이스가 홈 아래 몇 단계에 있는지는 사람마다 다르다. 네 단계까지 훑는다
    for depth in range(1, 5):
        pattern = os.path.join(home, *["*"] * depth, ".claude", "settings.json")
        roots += [os.path.dirname(os.path.dirname(p)) for p in glob.glob(pattern)]
    for root in roots:
        path = os.path.join(root, ".claude", "settings.json")
        if path in seen or not os.path.exists(path):
            continue
        seen.add(path)
        entry = load(path).get("statusLine")
        if any_plmi(entry):
            out.append((path, entry.get("command", "")))
    return out


def load(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        text = f.read().strip()
    return json.loads(text) if text else {}


def sweep(path):
    """뗀 뒤에 남는 것을 치운다.

    우리 말고는 아무것도 안 든 settings.json 은 우리가 만든 것이다. 남겨 두면 빈 `{}`
    파일이 워크스페이스마다 쌓인다. 백업도 붙어 있는 동안 되돌리려고 둔 것이라 뗄 때
    같이 치운다.
    """
    gone = []
    # 백업을 먼저 치운다. 뒤에 두면 폴더가 안 비어 그대로 남는다
    for backup in glob.glob(f"{path}.bak_*_plmi"):
        os.remove(backup)
        gone.append(backup)
    if os.path.exists(path) and not load(path):
        os.remove(path)
        gone.append(path)
        room = os.path.dirname(path)
        if os.path.isdir(room) and not os.listdir(room):
            os.rmdir(room)
            gone.append(room)
    for g in gone:
        print(f"  치움 {g}")


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
    어느 python3 에서나 돈다.

    셸로 감싸 stderr 를 버린다. `plmi --uninstall` 없이 `brew uninstall plmi` 를 하면
    이 경로가 사라지는데, 그때 파이썬이 뱉는 「No such file」이 상태줄 자리에 그대로
    찍힌다. 그 시점엔 `plmi` 명령도 없어서 떼지도 못한다. Formula 에는 제거 훅이 없어
    (uninstall_preflight 는 Cask 전용) 순서를 강제할 방법이 없으므로, 순서를 안 지켜도
    조용히 비어 있게 만든다.
    """
    return f"PLMI_SIZE={size} sh -c 'exec python3 {RUNNER} 2>/dev/null'"


def any_plmi(entry):
    """어느 판이든 플밍이면 True.

    `mine` 은 지금 이 파일이 낸 경로만 알아본다. 붙인 자리를 찾을 때는 그것으로 부족하다.
    brew 로 깐 것, 클론해 쓰는 것, 옛 경로에 남은 것이 다 다른 경로를 갖는다.
    """
    if not isinstance(entry, dict):
        return False
    cmd = str(entry.get("command", ""))
    return "PLMI_SIZE" in cmd and "statusline.py" in cmd


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
    ap.add_argument("--preview", metavar="초", type=float, nargs="?", const=4.0,
                    help="붙이지 않고 그 크기로 돌려 본다. 초를 주면 그만큼")
    ap.add_argument("--state", default="숨쉬기",
                    help="--preview 로 볼 상태. 기본은 숨쉬기")
    ap.add_argument("--bake", metavar="칸수", type=int,
                    help="그 칸 수로 스프라이트를 구워 둔다. 줄 수는 굽고 나서 정해진다")
    ap.add_argument("--dir", metavar="폴더",
                    help="project 스코프로 붙일 워크스페이스. 비우면 지금 폴더")
    ap.add_argument("--where", action="store_true",
                    help="지금 어디에 붙어 있는지 찾아 보여 준다")
    ap.add_argument("--uninstall", action="store_true", help="statusLine 을 뗀다")
    ap.add_argument("--force", action="store_true", help="다른 statusLine 이 있어도 덮는다")
    ap.add_argument("--dry-run", action="store_true", help="쓰지 않고 보여만 준다")
    a = ap.parse_args()

    if not os.path.exists(RUNNER):
        sys.exit(f"statusline.py 를 못 찾았다: {RUNNER}")
    if not SIZES:
        sys.exit("스프라이트가 없다. plmi/sprites/anim 을 확인할 것")

    if a.preview:
        return preview(a.size, a.preview, a.state)
    if a.bake:
        if a.bake < 8:
            sys.exit("칸이 너무 좁다. 8칸 이상")
        return bake(a.bake)
    if a.where:
        found = installed_at()
        for where, cmd in found:
            print(where)
            print(f"  {cmd}")
        if not found:
            print("붙어 있는 곳이 없다")
        return 0
    if a.dir and a.scope != "project":
        sys.exit("--dir 은 --scope project 와 함께 쓴다")
    if a.dir and not os.path.isdir(os.path.expanduser(a.dir)):
        sys.exit(f"그런 폴더가 없다: {a.dir}")
    if not a.uninstall and not fits(a.size) and not a.force:
        cols, rows = shutil.get_terminal_size((80, 24))
        sys.exit(f"{a.size} 는 지금 창({cols}x{rows})보다 크다. 줄바꿈으로 그림이 무너진다.\n"
                 f"들어가는 크기 = {', '.join(s for s in SIZES if fits(s)) or '없다'}\n"
                 "그래도 붙이려면 --force")
    path = settings_path(a.scope, a.dir)
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
            sweep(path)
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
