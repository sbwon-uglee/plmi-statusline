"""설치기를 무작위 명령 순서로 돌리며 늘 지켜야 하는 것을 본다.

한 번 붙이고 떼는 검사는 명령이 이어질 때 생기는 일을 못 본다. `--force` 로 덮고 떼면 원래
설정 백업까지 지워지던 일이 그랬다. 시작 설정마다 명령 하나씩과 둘씩은 빠짐없이 돌리고, 더 긴
순서는 씨앗으로 만든다. 무작위만 쓰면 적은 반복에서 어떤 짝을 한 번도 안 지나간다. 명령마다 아래를 본다.

- 트레이스백이 안 난다. 거절할 때는 까닭을 말한다
- 사용자가 둔 다른 키와 다른 파일은 그대로다. 못 읽는 settings.json 은 한 바이트도 안 바뀐다
- 덮은 남의 statusLine 은 지금 설정이나 백업 어딘가에 늘 남아 있다
- 심볼릭 링크인 settings.json 은 링크로 남는다
- --dry-run, --preview, --where 는 아무것도 안 바꾼다
- 붙이기가 성공하면 이 사본의 플밍이가 붙어 있고, 떼기가 성공하면 statusLine 이 없다
"""
import concurrent.futures
import json
import os
import random
import subprocess
import sys
import tempfile

import grid

INSTALL = os.path.join(grid.ROOT, "plmi", "install.py")
SEQS = grid.times(16)
FOREIGN = {"type": "command", "command": "echo 남의것"}
OTHER_COPY = {"type": "command", "command": "PLMI_SIZE=16x8 python3 /다른/사본/statusline.py"}
# README 대로 명령 앞에 변수를 붙이고 필드를 더한 플밍이. 다시 붙여도 둘 다 남아야 한다
TUNED = {"type": "command", "padding": 0,
         "command": "PLMI_BUBBLE=0 PLMI_SIZE=16x8 sh -c 'exec python3 \"$0\" 2>/dev/null' /다른/사본/statusline.py"}
# 플밍이에 다른 명령을 이어 붙인 것. 사람이 만든 것이라 남의 것으로 다룬다
MIXED = {"type": "command",
         "command": "input=$(cat); echo \"$input\" | PLMI_SIZE=26x11 python3 ~/plmi/plmi/statusline.py; echo 다른것"}
USER_KEYS = {"permissions": {"allow": ["Bash(ls:*)"]}, "model": "opus"}


def _plmi(entry):
    cmd = str((entry or {}).get("command", "")) if isinstance(entry, dict) else ""
    return "PLMI_SIZE" in cmd and "statusline.py" in cmd


def _snapshot(room):
    """폴더 안 파일 이름, 링크 여부, 내용."""
    out = {}
    if not os.path.isdir(room):
        return out
    for base, dirs, files in os.walk(room):
        for name in files:
            path = os.path.join(base, name)
            rel = os.path.relpath(path, room)
            link = os.readlink(path) if os.path.islink(path) else None
            try:
                with open(path, "rb") as f:
                    body = f.read()
            except OSError:
                body = None
            out[rel] = (link, body)
    return out


KINDS = ["없음", "빈 폴더", "빈 설정", "다른 키", "남의 것", "남의 것과 다른 키",
         "다른 사본", "깨짐", "목록", "링크", "남의 것 링크", "사용자 파일",
         "손본 플밍이", "섞인 명령", "문자열 statusLine", "읽기 전용", "링크 폴더"]
# 시작 설정의 statusLine 이 남의 것인지. 검사 대상 코드의 판정을 빌려 쓰지 않고 여기서 정해 둔다
THEIRS = {"남의 것": FOREIGN, "남의 것과 다른 키": FOREIGN, "섞인 명령": MIXED, "문자열 statusLine": "echo hi"}
# 어떤 명령에도 바이트 하나 안 바뀌어야 하는 시작 설정
FROZEN = ("깨짐", "목록", "읽기 전용")


def _start(kind, d):
    """시작 설정을 만들고 (워크스페이스, 이름, 파싱된 값, 사용자 파일 목록, 링크 대상) 을 돌려준다."""
    ws = os.path.join(d, "ws [1]")                  # glob 이 특수 문자로 읽는 괄호
    room = os.path.join(ws, ".claude")
    os.makedirs(ws)
    path = os.path.join(room, "settings.json")
    data, extra, target = None, [], None
    if kind == "없음":
        return ws, kind, None, extra, target
    if kind == "링크 폴더":
        real = os.path.join(d, "dotfiles", "claude")
        os.makedirs(real)
        os.symlink(real, room)
        return ws, kind, None, extra, real
    os.makedirs(room)
    if kind == "빈 폴더":
        return ws, kind, None, extra, target
    raw = None
    if kind == "빈 설정":
        data = {}
    elif kind == "다른 키":
        data = dict(USER_KEYS)
    elif kind == "남의 것":
        data = {"statusLine": FOREIGN}
    elif kind == "남의 것과 다른 키":
        data = dict(USER_KEYS, statusLine=FOREIGN)
    elif kind == "다른 사본":
        data = {"statusLine": OTHER_COPY}
    elif kind == "깨짐":
        raw = "{깨진"
    elif kind == "목록":
        raw = "[1, 2]"
    elif kind in ("링크", "남의 것 링크"):
        data = dict(USER_KEYS) if kind == "링크" else {"statusLine": OTHER_COPY}
        target = os.path.join(d, "dotfiles", "settings.json")
        os.makedirs(os.path.dirname(target))
        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.symlink(target, path)
        return ws, kind, data, extra, target
    elif kind == "손본 플밍이":
        data = dict(USER_KEYS, statusLine=TUNED)
    elif kind == "섞인 명령":
        data = {"statusLine": MIXED}
    elif kind == "문자열 statusLine":
        data = {"statusLine": "echo hi"}
    elif kind == "읽기 전용":
        data = dict(USER_KEYS, statusLine=OTHER_COPY)
    elif kind == "사용자 파일":
        data = dict(USER_KEYS)
        for rel in ("settings.local.json", os.path.join("commands", "x.md")):
            p = os.path.join(room, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write("사용자 것\n")
            extra.append(rel)
    with open(path, "w", encoding="utf-8") as f:
        f.write(raw if raw is not None else json.dumps(data, ensure_ascii=False))
    if kind == "읽기 전용":
        os.chmod(path, 0o444)
    return ws, kind, data, extra, target


OPS = [
    ["붙이기"], ["붙이기", "--force"], ["붙이기", "--dry-run"], ["붙이기", "--size"],
    ["--uninstall"], ["--uninstall", "--force"], ["--uninstall", "--dry-run"],
    ["--preview", "0"], ["--where"],
]


def _run(op, ws, home, rng, scope):
    """scope 가 user 면 HOME 을 워크스페이스로 두어 같은 settings.json 을 보게 한다."""
    args = [a for a in op if a != "붙이기"]
    if "--size" in args:
        args = args + [rng.choice(grid.sizes())]
    where = ["--scope", "project", "--dir", ws] if scope == "project" else ["--scope", "user"]
    env = dict(os.environ, HOME=home if scope == "project" else ws, COLUMNS="200", LINES="60")
    return args, subprocess.run([sys.executable, INSTALL, *where, *args],
                                capture_output=True, text=True, timeout=60, env=env)


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _play(kind, ops, rng, label, scope="project"):
    """시작 설정 kind 에서 ops 를 차례로 돌리며 명령마다 불변식을 본다."""
    with tempfile.TemporaryDirectory() as d:
        home = os.path.join(d, "home")
        os.makedirs(home)
        ws, kind, data, extra, target = _start(kind, d)
        room = os.path.join(ws, ".claude")
        path = os.path.join(room, "settings.json")
        first = _snapshot(room)
        keys = {k: v for k, v in (data or {}).items() if k != "statusLine"}
        foreign = THEIRS.get(kind)
        history = []
        for op in ops:
            before = _snapshot(room)
            prev = _read(path) if os.path.exists(path) else None
            prev = prev.get("statusLine") if isinstance(prev, dict) else None
            tuned = isinstance(prev, dict) and prev.get("padding") == 0
            args, out = _run(op, ws, home, rng, scope)
            history.append(" ".join(args) or "(붙이기)")
            where = f"{label} [{kind}, {scope}] {' → '.join(history)}"
            assert "Traceback" not in out.stderr, f"{where}\n{out.stderr[-500:]}"
            if out.returncode != 0:
                assert out.stderr.strip(), f"{where}: 까닭 없이 멈췄다"

            now = _read(path) if os.path.exists(path) else None
            if kind in FROZEN:
                assert _snapshot(room) == first, f"{where}: 못 읽거나 못 쓰는 설정을 건드렸다"
                continue
            if isinstance(now, dict):
                for k, v in keys.items():
                    assert now.get(k) == v, f"{where}: {k} 가 바뀌거나 사라졌다"
            else:
                assert not keys, f"{where}: 다른 키가 든 설정이 없어졌다"
            for rel in extra:
                assert first[rel] == _snapshot(room).get(rel), f"{where}: 사용자 파일 {rel} 이 바뀌었다"
            if target:
                link = room if kind == "링크 폴더" else path
                assert os.path.islink(link) and os.readlink(link) == target, f"{where}: 링크가 끊겼다"
            if foreign:
                kept = [now.get("statusLine")] if isinstance(now, dict) else []
                for name in os.listdir(room) if os.path.isdir(room) else []:
                    if "bak_" in name:
                        kept.append((_read(os.path.join(room, name)) or {}).get("statusLine"))
                assert foreign in kept, f"{where}: 덮은 남의 statusLine 이 어디에도 없다"
            if "--dry-run" in args or "--preview" in args or "--where" in args:
                assert _snapshot(room) == before, f"{where}: 바꾸지 않아야 하는 명령이 바꿨다"
            elif out.returncode == 0 and "--uninstall" in args:
                assert not (isinstance(now, dict) and "statusLine" in now), f"{where}: 뗐는데 남았다"
                for name in os.listdir(room) if os.path.isdir(room) else []:
                    if "bak_" in name:
                        left = (_read(os.path.join(room, name)) or {}).get("statusLine")
                        assert foreign is not None and left == foreign, f"{where}: 쓸모없는 백업 {name} 이 남았다"
            elif out.returncode == 0:
                line = now.get("statusLine") if isinstance(now, dict) else {}
                mine = os.path.join(grid.ROOT, "plmi", "statusline.py")
                assert _plmi(line) and mine in line["command"], f"{where}: 붙였다는데 이 사본의 플밍이가 아니다 {line}"
                if tuned:
                    assert "PLMI_BUBBLE=0" in line["command"] and line.get("padding") == 0, \
                        f"{where}: 사람이 붙인 변수나 필드가 사라졌다 {line}"


def _all(jobs):
    """(시작 설정, 명령 목록, 라벨, 스코프) 를 동시에 돌린다. 하나라도 실패하면 그 실패를 올린다."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, os.cpu_count() or 4)) as pool:
        for f in [pool.submit(_play, kind, ops, random.Random(0), label, scope)
                  for kind, ops, label, scope in jobs]:
            f.result()


def test_시작_설정마다_명령_하나씩():
    _all([(kind, [op], "하나씩", "project" if i % 2 else "user")
          for i, kind in enumerate(KINDS) for op in OPS])


@grid.slow
def test_시작_설정마다_명령_둘씩():
    _all([(kind, [a, b], "둘씩", "user" if (i + j) % 2 else "project")
          for i, kind in enumerate(KINDS) for j, a in enumerate(OPS) for b in OPS])


def test_무작위로_이은_명령():
    for seed in range(SEQS):
        rng = random.Random(seed)
        ops = [rng.choice(OPS) for _ in range(rng.randint(3, 6))]
        _play(rng.choice(KINDS), ops, rng, f"씨앗 {seed}", rng.choice(["project", "user"]))
