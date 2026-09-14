"""플밍이를 Claude Code statusLine 에 붙이거나 뗀다.

    python3 plmi/install.py                 사용자 설정에 붙인다
    python3 plmi/install.py --size 36x16    큰 그림으로
    python3 plmi/install.py --scope project 지금 폴더의 .claude 에만
    python3 plmi/install.py --preview 10 --state 놀람   붙이지 않고 10초 돌려 본다
    python3 plmi/install.py --where         붙어 있는 곳을 찾는다
    python3 plmi/install.py --bake 30       30칸으로 굽는다
    python3 plmi/install.py --scope project --dir ~/work/foo   그 워크스페이스의 .claude 에
    python3 plmi/install.py --uninstall     뗀다
    python3 plmi/install.py --force         플밍이가 아닌 statusLine 도 덮거나 떼고, 창 크기 검사를 건너뛴다
    python3 plmi/install.py --dry-run       쓸 내용만 보여 준다
    python3 plmi/install.py --version       깔린 판

statusLine 은 사용자나 프로젝트 settings.json 에 절대경로로 적는다. statusline.py 가
스프라이트를 자기 파일 기준으로 찾으므로 어느 폴더에서 Claude Code 를 띄우든 돈다.
"""
import argparse
import datetime
import glob
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

CELLAR = re.compile(r"(?P<prefix>.*)/Cellar/(?P<name>[^/]+)/[^/]+/(?P<rest>.*)")
ASSIGN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", re.S)
WRAP = "exec python3 \"$0\" 2>/dev/null"


def stable(path):
    """설정에 적을 경로. brew 의 `<prefix>/Cellar/<이름>/<버전>/` 아래면 버전이 없는
    `<prefix>/opt/<이름>/` 으로 바꾼다. Cellar 쪽을 적으면 다음 `brew upgrade` 가 그 폴더를
    지워 상태줄이 조용히 사라진다. 그 밖에는 링크를 푼 실제 경로를 쓴다.
    """
    real = os.path.realpath(path)
    m = CELLAR.match(real)
    if not m:
        return real
    opt = os.path.join(m.group("prefix"), "opt", m.group("name"), m.group("rest"))
    return opt if os.path.exists(opt) else real


HERE = os.path.dirname(stable(__file__))
RUNNER = os.path.join(HERE, "statusline.py")
sys.path.insert(0, HERE)
try:
    import statusline  # 크기 목록과 미리 보기를 상태줄과 같은 코드로 본다
    from bubble import COLS
except ImportError:
    sys.exit(f"statusline.py 를 못 찾았다: {RUNNER}")

BAKED = statusline.BAKED
SIZES = statusline.sizes()
DEFAULT_SIZE = statusline.default_size()
NO_SPRITES = "스프라이트가 없다. plmi/sprites/anim 을 확인할 것"
STATES = sorted({os.path.basename(f).split("_")[1]
                 for d in statusline.DIRS for f in glob.glob(os.path.join(glob.escape(d), "플밍이_*_*.json"))})
# 굽기가 받는 가장 작은 칸 수. 이보다 좁으면 머리가 잘리거나 얼굴 칸이 안 생긴다
MIN_COLS = 13
# 설치기를 부른 셸에서 켜 두면 명령에도 적는 변수. 창 크기 검사도 적힌 값으로 본다
CARRY = ("PLMI_BUBBLE", "PLMI_COLOR")


def version():
    try:
        with open(os.path.join(os.path.dirname(HERE), "VERSION"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "0.0.0"


def bake(cols, dry_run):
    """그 칸 수로 스프라이트를 구워 홈 아래에 둔다.

    줄 수는 굽고 나서 정해지므로 칸 수만 받는다. numpy 와 pillow 가 필요하다. `uv` 가 있으면
    그때만 받아 쓰고, 없으면 이미 깔린 것을 쓴다. 임시 폴더에 다 구운 뒤 그 칸 수의 옛 파일과
    바꾸므로 굽다 멈춰도 전에 구운 것은 남는다.
    """
    anim = os.path.join(HERE, "anim.py")
    art = os.path.join(os.path.dirname(HERE), "assets")
    if not os.path.exists(anim) or not os.path.isdir(art):
        sys.exit("굽는 데 필요한 파일이 없다. 저장소를 클론해 쓰거나 새 판으로 올려라")
    if shutil.which("uv"):
        # 부른 폴더의 파이썬 프로젝트를 따라가지 않게 한다. 따라가면 그 폴더에 .venv 가 생긴다
        cmd = ["uv", "run", "--no-project", "--quiet", "--with", "numpy", "--with", "pillow",
               "python", anim]
    else:
        probe = subprocess.run(["python3", "-c", "import numpy, PIL"], capture_output=True)
        if probe.returncode != 0:
            sys.exit("numpy 와 pillow 가 필요하다. uv 를 깔거나 pip install numpy pillow")
        cmd = ["python3", anim]
    if dry_run:
        print(f"{cols}칸으로 구워 {BAKED} 에 둔다\n  (--dry-run 이라 굽지 않았다)")
        return
    os.makedirs(BAKED, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="plmi-bake-", dir=BAKED)
    try:
        out = subprocess.run(cmd + ["--cols", str(cols), "--out", tmp], cwd=HERE)
        made = sorted(glob.glob(os.path.join(glob.escape(tmp), f"플밍이_*_{cols}x*.json")))
        if out.returncode != 0 or not made:
            sys.exit("굽다가 멈췄다. 전에 구운 크기는 그대로다")
        for old in glob.glob(os.path.join(glob.escape(BAKED), f"플밍이_*_{cols}x*.json")):
            os.remove(old)
        for f in made:
            os.replace(f, os.path.join(BAKED, os.path.basename(f)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    size = os.path.basename(made[0]).rsplit("_", 1)[1][:-5]
    print(f"구웠다. 붙이려면 plmi --size {size}")


def preview(size, secs, state):
    """붙이기 전에 그 크기와 상태를 secs 초 동안 돌려 보인다. 상태줄과 같은 panel 로 그린다."""
    statusline.SIZE = size
    art = statusline.panel(state, "")
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


def width(size, bubble):
    """그 크기를 그렸을 때 한 줄의 칸 수. 말풍선은 그림과 한 칸 띄우고 안쪽 COLS 칸에 테두리와 여백 네 칸이다."""
    return int(size.split("x")[0]) + (1 + COLS + 4 if bubble else 0)


def misfit(size, bubble):
    """지금 창에 안 들어가는 까닭. 들어가면 빈 문자열."""
    cols, rows = shutil.get_terminal_size((80, 24))
    w, h = width(size, bubble), int(size.split("x")[1])
    why = []
    if w > cols:
        tip = " 말풍선을 끄려면 PLMI_BUBBLE=0 을 앞에 붙여 다시 부른다." if bubble else ""
        why.append(f"{size} 는 {'말풍선까지 ' if bubble else ''}{w}칸이라 창 폭 {cols}칸에 안 들어간다. "
                   f"줄바꿈으로 그림이 무너진다.{tip}")
    if h >= rows:
        why.append(f"{size} 는 {h}줄이라 창 높이 {rows}줄에 안 들어간다.")
    return "\n".join(why)


def settings_path(scope, where=None):
    """붙일 settings.json 경로. user 는 ~/.claude, project 는 where(비우면 지금 폴더) 아래 .claude."""
    if scope == "user":
        return os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
    root = os.path.abspath(os.path.expanduser(where or os.getcwd()))
    return os.path.join(root, ".claude", "settings.json")


def known_projects(home):
    """Claude Code 가 ~/.claude.json 에 기억하는 워크스페이스 경로."""
    try:
        with open(os.path.join(home, ".claude.json"), encoding="utf-8") as f:
            projects = json.load(f).get("projects")
    except (OSError, ValueError, AttributeError):
        return []
    return [p for p in projects if isinstance(p, str)] if isinstance(projects, dict) else []


def installed_at():
    """플밍이가 붙은 settings.json 을 (경로, 명령) 으로. 찾아본 곳을 말하는 문장도 같이 돌려준다.

    홈, Claude Code 가 기억하는 워크스페이스, 홈 아래 네 단계를 본다. ~/Library 와 숨김 폴더는
    훑지 않는다. 맥이 다른 앱 데이터에 접근한다는 창을 띄울 수 있고 느리다.
    """
    home = os.path.expanduser("~")
    projects = known_projects(home)
    roots = [home] + projects
    for top in sorted(os.listdir(home)) if os.path.isdir(home) else []:
        base = os.path.join(home, top)
        if top.startswith(".") or top == "Library" or not os.path.isdir(base):
            continue
        for depth in range(0, 4):
            pattern = os.path.join(glob.escape(base), *["*"] * depth, ".claude", "settings.json")
            roots += [os.path.dirname(os.path.dirname(p)) for p in glob.glob(pattern)]
    seen, out = set(), []
    for root in roots:
        path = os.path.join(root, ".claude", "settings.json")
        real = os.path.realpath(path)
        if real in seen or not os.path.exists(path):
            continue
        seen.add(real)
        try:
            data = load(path)
        except (OSError, ValueError):
            continue                      # 읽을 수 없는 설정 파일은 건너뛴다
        entry = data.get("statusLine") if isinstance(data, dict) else None
        if plmi_env(entry) is not None:
            out.append((path, entry.get("command", "")))
    looked = (f"찾아본 곳 = 홈, Claude Code 가 기억하는 워크스페이스 {len(projects)}곳, "
              "홈 아래 네 단계(Library 와 숨김 폴더 빼고)")
    return out, looked


def load(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        text = f.read().strip()
    return json.loads(text) if text else {}


def sweep(path):
    """statusLine 을 뺀 뒤 비어 있는 settings.json 과 빈 .claude 폴더, `.bak_*_plmi` 백업을 지운다.

    플밍이만 든 명령이 아닌 statusLine 이 든 백업은 남긴다. `--force` 로 덮기 전의 원래 설정이다.
    settings.json 이나 .claude 가 심볼릭 링크면 비어도 남긴다. dotfiles 로 관리하는 설정이다.
    """
    gone = []
    # 백업을 먼저 치운다. 뒤에 두면 폴더가 안 비어 그대로 남는다
    for backup in sorted(glob.glob(glob.escape(path) + ".bak_*_plmi")):
        try:
            old = load(backup).get("statusLine")
        except (OSError, ValueError, AttributeError):
            continue                      # 못 읽는 백업은 무엇이 들었는지 몰라 남긴다
        if old and plmi_env(old) is None:
            print(f"  남김 {backup}  플밍이 전 statusLine 이 들어 있다")
            continue
        os.remove(backup)
        gone.append(backup)
    if os.path.exists(path) and not os.path.islink(path) and not load(path):
        os.remove(path)
        gone.append(path)
        room = os.path.dirname(path)
        if os.path.isdir(room) and not os.path.islink(room) and not os.listdir(room):
            os.rmdir(room)
            gone.append(room)
    for g in gone:
        print(f"  치움 {g}")


def save(path, data, backup=True):
    """backup 이면 쓰기 전에 백업한다. 사람이 손으로 만든 설정이 들어 있는 파일이다.

    쓸 수 없는 파일이면 백업도 안 뜨고 멈춘다. 보통 파일은 옆에 다 쓴 뒤 바꿔 끼워 Claude Code 가
    반쯤 쓴 파일을 읽지 않게 하고, 심볼릭 링크는 링크를 살리도록 가리키는 파일에 바로 쓴다.
    """
    room = os.path.dirname(path)
    try:
        os.makedirs(room, exist_ok=True)
    except OSError as e:
        sys.exit(f"설정 폴더를 만들 수 없다: {room} ({e.strerror})")
    if os.path.exists(path) and not os.access(path, os.W_OK) or not os.access(room, os.W_OK):
        sys.exit(f"설정 파일에 쓸 수 없다: {path}")
    if backup and os.path.exists(path):
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        bak, n = f"{path}.bak_{stamp}_plmi", 1
        while os.path.exists(bak):                 # 같은 초에 두 번 떠도 앞 백업을 덮지 않게 이름을 바꾼다
            bak, n = f"{path}.bak_{stamp}-{n}_plmi", n + 1
        shutil.copy2(path, bak)
        print(f"  백업 {bak}")
    body = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if os.path.islink(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        return
    fd, tmp = tempfile.mkstemp(prefix=".settings-", dir=room)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(body)
    if os.path.exists(path):
        shutil.copymode(path, tmp)
    else:
        mask = os.umask(0)
        os.umask(mask)
        os.chmod(tmp, 0o666 & ~mask)               # mkstemp 는 0600 으로 만든다. 새 파일은 보통 파일 권한으로
    os.replace(tmp, path)


def plmi_env(entry):
    """statusLine 이 플밍이만 부르는 명령이면 앞에 붙은 환경변수를 순서대로, 아니면 None.

    명령 전체가 `[변수=값 ...] sh -c '<WRAP>' <경로>/statusline.py` 나 옛 모양
    `[변수=값 ...] python3 <경로>/statusline.py` 이고 PLMI_SIZE 가 있어야 한다. 설치 경로는 사본마다
    달라 보지 않는다. 다른 명령이 섞인 것은 사람이 손본 statusLine 이라 남의 것으로 본다.
    """
    if not isinstance(entry, dict):
        return None
    try:
        words = shlex.split(str(entry.get("command", "")))
    except ValueError:
        return None
    env = {}
    while words and ASSIGN.match(words[0]):
        key, value = ASSIGN.match(words.pop(0)).groups()
        env[key] = value
    if "PLMI_SIZE" not in env:
        return None
    if words[:3] == ["sh", "-c", WRAP] and len(words) == 4 or words[:1] == ["python3"] and len(words) == 2:
        if words[-1].endswith("statusline.py"):
            return env
    return None


def command(size, env=None):
    """settings.json 에 적을 상태줄 명령. env 는 앞에 남길 환경변수다.

    PATH 의 python3 로 부르고 stderr 는 버린다. 파이썬이 바뀌거나 `brew uninstall` 로 경로가
    사라져도 상태줄에 오류가 찍히지 않는다.
    """
    env = dict(env or {})
    env["PLMI_SIZE"] = size
    head = " ".join(f"{k}={shlex.quote(v)}" for k, v in env.items())
    # 공백이 든 경로도 한 인자로 가도록 sh -c 의 $0 으로 넘긴다
    return f"{head} sh -c {shlex.quote(WRAP)} {shlex.quote(RUNNER)}"


def shown(entry):
    return entry.get("command") if isinstance(entry, dict) else json.dumps(entry, ensure_ascii=False)


def parser():
    ap = argparse.ArgumentParser(description="플밍이 statusLine 설치")
    ap.add_argument("--version", action="version", version=version())
    ap.add_argument("--size", default=DEFAULT_SIZE, choices=SIZES or None,
                    help=f"그림 크기. 있는 것 = {', '.join(SIZES)}")
    ap.add_argument("--scope", default="user", choices=("user", "project"),
                    help="user 는 ~/.claude, project 는 --dir 폴더(없으면 지금 폴더)의 .claude")
    ap.add_argument("--preview", metavar="초", type=float, nargs="?", const=4.0,
                    help="붙이지 않고 그 크기로 돌려 본다. 초를 주면 그만큼")
    ap.add_argument("--state", default="숨쉬기", choices=STATES or None,
                    help="--preview 로 볼 상태. 기본은 숨쉬기")
    ap.add_argument("--bake", metavar="칸수", type=int,
                    help="그 칸 수로 스프라이트를 구워 둔다. 줄 수는 굽고 나서 정해진다")
    ap.add_argument("--dir", metavar="폴더",
                    help="project 스코프로 붙일 워크스페이스. 비우면 지금 폴더")
    ap.add_argument("--where", action="store_true",
                    help="지금 어디에 붙어 있는지 찾아 보여 준다")
    ap.add_argument("--uninstall", action="store_true", help="statusLine 을 뗀다")
    ap.add_argument("--force", action="store_true", help="플밍이가 아닌 statusLine 도 덮거나 떼고, 창 크기 검사를 건너뛴다")
    ap.add_argument("--dry-run", action="store_true", help="쓰지 않고 보여만 준다")
    return ap


def main():
    a = parser().parse_args()

    # 굽기, 찾기, 떼기는 스프라이트가 없어도 한다
    if a.bake is not None:
        if a.bake < MIN_COLS:
            sys.exit(f"칸이 너무 좁다. {MIN_COLS}칸 이상")
        return bake(a.bake, a.dry_run)
    if a.where:
        found, looked = installed_at()
        for where, cmd in found:
            print(where)
            print(f"  {cmd}")
        if not found:
            print(f"붙어 있는 곳을 못 찾았다. {looked}")
        return
    if a.preview is not None:
        if not SIZES:
            sys.exit(NO_SPRITES)
        return preview(a.size, a.preview, a.state)
    if a.dir and a.scope != "project":
        sys.exit("--dir 은 --scope project 와 함께 쓴다")
    if a.dir and not os.path.isdir(os.path.expanduser(a.dir)):
        sys.exit(f"그런 폴더가 없다: {a.dir}")
    path = settings_path(a.scope, a.dir)
    try:
        data = load(path)
    except (OSError, ValueError):
        data = None
    if not isinstance(data, dict):
        sys.exit(f"settings.json 을 읽을 수 없다: {path}")
    now = data.get("statusLine")
    ours = plmi_env(now)

    if a.uninstall:
        if not now:
            print("붙어 있는 statusLine 이 없다")
            return
        if ours is None and not a.force:
            sys.exit(f"플밍이만 부르는 statusLine 이 아니다. 그대로 둔다. 떼려면 --force\n  {shown(now)}")
        data.pop("statusLine", None)
        print(f"뗀다: {path}")
        if not a.dry_run:
            # 플밍이를 뗄 때는 백업을 뜨지 않는다. 남의 statusLine 을 뗄 때만 떠서 sweep 이 남긴다
            save(path, data, backup=ours is None)
            sweep(path)
        else:
            print("  (--dry-run 이라 쓰지 않았다)")
        return

    if not SIZES:
        sys.exit(NO_SPRITES)
    env = dict(ours or {})
    env.update({k: os.environ[k] for k in CARRY if k in os.environ})
    line = command(a.size, env)
    # 남의 statusLine 을 먼저 알린다. 창 크기 때문에 --force 를 붙인 사람이 모르고 덮지 않게 한다
    if now and ours is None and not a.force:
        sys.exit("이미 다른 statusLine 이 있다. 덮으려면 --force\n"
                 f"  지금: {shown(now)}\n"
                 f"  넣으려던 것: {line}")
    why = misfit(a.size, env.get("PLMI_BUBBLE", "1") != "0")
    if why and not a.force:
        sys.exit(f"{why}\n"
                 f"들어가는 크기 = {', '.join(s for s in SIZES if not misfit(s, env.get('PLMI_BUBBLE', '1') != '0')) or '없다'}\n"
                 "그래도 붙이려면 --force")

    entry = dict(now) if ours is not None else {}
    entry.update({"type": "command", "command": line})
    entry.setdefault("refreshInterval", 1)
    data["statusLine"] = entry
    print(f"설정 파일 {path}")
    print("  " + json.dumps(entry, ensure_ascii=False))
    if a.dry_run:
        print("  (--dry-run 이라 쓰지 않았다)")
        return
    save(path, data)
    print("붙였다. Claude Code 를 다시 띄우면 플밍이가 나온다")


if __name__ == "__main__":
    main()
