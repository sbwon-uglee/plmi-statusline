"""설치기가 사람에게 보이는 것: 안내와 거절 문구, 경계값, 굽기, 찾기, 파일 모양.

상태 기계 검사는 설정을 잃지 않는지를 보고 문구는 안 본다. 여기서는 길마다 무엇을 말하고
어떤 종료 코드로 끝나는지, 경계 한 칸 앞뒤에서 갈리는지를 적어 둔다.
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile

import grid

PLMI = os.path.join(grid.ROOT, "plmi")
INSTALL = os.path.join(PLMI, "install.py")
sys.path.insert(0, PLMI)
import install  # noqa: E402

MADE = """import os, sys
out = sys.argv[sys.argv.index("--out") + 1]
cols = sys.argv[sys.argv.index("--cols") + 1]
os.makedirs(out, exist_ok=True)
for s in ("숨쉬기", "작업중"):
    open(os.path.join(out, "플밍이_%s_%sx9.json" % (s, cols)), "w").write("{}")
"""


def _shim(d, has_numpy):
    """PATH 에 둘 python3. uv 는 안 둔다. numpy 확인에 has_numpy 대로 답하고 나머지는 이 파이썬으로 넘긴다."""
    room = os.path.join(d, "shim")
    os.makedirs(room, exist_ok=True)
    path = os.path.join(room, "python3")
    with open(path, "w") as f:
        # numpy 가 없으면 진짜 파이썬처럼 stderr 에 오류를 찍는다. 설치기가 그걸 사람에게 흘리면 안 된다
        f.write('#!/bin/sh\nif [ "$1" = "-c" ] && [ "$2" = "import numpy, PIL" ]; then\n'
                '  [ %d = 0 ] && exit 0\n  echo "ModuleNotFoundError: No module named numpy" >&2; exit 1\nfi\n'
                'exec "%s" "$@"\n' % (0 if has_numpy else 1, sys.executable))
    os.chmod(path, 0o755)
    return os.pathsep.join([room, "/usr/bin", "/bin"])


def _copy(d, anim=None, assets=True, sprites=True, version=True):
    root = os.path.join(d, "copy")
    ignore = ["__pycache__"] + ([] if sprites else ["anim"])
    shutil.copytree(PLMI, os.path.join(root, "plmi"), ignore=shutil.ignore_patterns(*ignore))
    if assets:
        os.makedirs(os.path.join(root, "assets"))
    if version:
        shutil.copy(os.path.join(grid.ROOT, "VERSION"), root)
    target = os.path.join(root, "plmi", "anim.py")
    if anim is None:
        os.remove(target)
    else:
        with open(target, "w", encoding="utf-8") as f:
            f.write(anim)
    return os.path.join(root, "plmi", "install.py")


def _run(args, home, script=INSTALL, cols="200", lines="60", **env):
    full = dict(os.environ, HOME=home, COLUMNS=cols, LINES=lines, **env)
    out = subprocess.run([sys.executable, script, *args], capture_output=True, text=True, timeout=120, env=full)
    assert "Traceback" not in out.stderr, out.stderr[-500:]
    return out.returncode, out.stdout + out.stderr


def test_창_폭과_높이는_한_칸_앞뒤에서_갈린다():
    small = grid.sizes()[-1]
    w, h = (int(x) for x in small.split("x"))
    need = w + 1 + install.COLS + 4
    with tempfile.TemporaryDirectory() as d:
        ws = os.path.join(d, "ws")
        os.makedirs(ws)
        base = ["--scope", "project", "--dir", ws, "--size", small, "--dry-run"]
        rc, said = _run(base, d, cols=str(need - 1))
        assert rc != 0 and f"말풍선까지 {need}칸이라 창 폭 {need - 1}칸" in said and "PLMI_BUBBLE=0" in said, said
        assert _run(base, d, cols=str(need))[0] == 0
        rc, said = _run(base, d, cols=str(w - 1), PLMI_BUBBLE="0")
        assert rc != 0 and f"{w}칸이라 창 폭 {w - 1}칸" in said and "말풍선까지" not in said, said
        assert _run(base, d, cols=str(w), PLMI_BUBBLE="0")[0] == 0
        rc, said = _run(base, d, lines=str(h))
        assert rc != 0 and f"{h}줄이라 창 높이 {h}줄" in said, said
        assert _run(base, d, lines=str(h + 1))[0] == 0


def test_안_들어가면_들어가는_크기를_알려_준다():
    sizes = grid.sizes()
    with tempfile.TemporaryDirectory() as d:
        ws = os.path.join(d, "ws")
        os.makedirs(ws)
        base = ["--scope", "project", "--dir", ws, "--size", sizes[0], "--dry-run"]
        cols = int(sizes[-1].split("x")[0]) + 27
        rc, said = _run(base, d, cols=str(cols))
        fit = [s for s in sizes if int(s.split("x")[0]) + 27 <= cols]
        assert rc != 0 and f"들어가는 크기 = {', '.join(fit)}" in said, said
        rc, said = _run(base, d, cols=str(int(sizes[1].split("x")[0])), PLMI_BUBBLE="0")
        fit = [s for s in sizes if int(s.split("x")[0]) <= int(sizes[1].split("x")[0])]
        assert rc != 0 and f"들어가는 크기 = {', '.join(fit)}" in said, said
        rc, said = _run(base, d, cols="5")
        assert "들어가는 크기 = 없다" in said, said


def test_붙이고_떼는_길마다_무엇을_했는지_말한다():
    with tempfile.TemporaryDirectory() as d:
        ws = os.path.join(d, "ws")
        os.makedirs(ws)
        where = ["--scope", "project", "--dir", ws]
        rc, said = _run(where + ["--uninstall"], d)
        assert rc == 0 and "붙어 있는 statusLine 이 없다" in said, said
        rc, said = _run(where + ["--dry-run"], d)
        assert rc == 0 and "(--dry-run 이라 쓰지 않았다)" in said and not os.path.exists(os.path.join(ws, ".claude"))
        rc, said = _run(where, d, PLMI_COLOR="안씀")
        assert rc == 0 and "설정 파일" in said and '"refreshInterval": 1' in said and "붙였다" in said, said
        assert "PLMI_COLOR=안씀" in said or "PLMI_COLOR='안씀'" in said, f"보여 주는 설정의 한글이 풀려 나왔다: {said}"
        rc, said = _run(where, d)
        assert rc == 0 and "백업" in said, said
        rc, said = _run(where + ["--uninstall", "--dry-run"], d)
        assert rc == 0 and "(--dry-run 이라 쓰지 않았다)" in said, said
        rc, said = _run(where + ["--uninstall"], d)
        room = os.path.join(ws, ".claude")
        assert rc == 0 and "뗀다:" in said, said
        lines = said.split("\n")
        assert any(l.startswith("  치움 ") and ".bak_" in l for l in lines), f"백업을 치웠다고 안 했다: {said}"
        for gone in (os.path.join(room, "settings.json"), room):
            assert f"  치움 {gone}" in lines, f"{gone} 를 치웠다고 안 했다: {said}"
        rc, said = _run(["--scope", "project", "--dir", os.path.join(d, "없는")], d)
        assert rc != 0 and "그런 폴더가 없다" in said, said


def test_남의_statusLine_은_그대로_보여_주며_거절한다():
    with tempfile.TemporaryDirectory() as d:
        ws = os.path.join(d, "ws")
        os.makedirs(os.path.join(ws, ".claude"))
        where = ["--scope", "project", "--dir", ws]
        for line, shown in (({"type": "command", "command": "echo 남의것"}, "echo 남의것"), ("안녕 상태줄", '"안녕 상태줄"')):
            with open(os.path.join(ws, ".claude", "settings.json"), "w", encoding="utf-8") as f:
                json.dump({"statusLine": line}, f, ensure_ascii=False)
            rc, said = _run(where, d)
            assert rc != 0 and "이미 다른 statusLine" in said and f"지금: {shown}" in said, said
            rc, said = _run(where + ["--uninstall"], d)
            assert rc != 0 and "플밍이만 부르는 statusLine 이 아니다" in said and shown in said, said


def test_없는_크기와_상태는_인자에서_막는다():
    with tempfile.TemporaryDirectory() as d:
        assert _run(["--size", "99x99", "--dry-run"], d)[0] == 2
        assert _run(["--preview", "0", "--state", "없는상태"], d)[0] == 2


def test_스프라이트나_VERSION_이_없는_사본의_안내():
    with tempfile.TemporaryDirectory() as d:
        script = _copy(d, anim=MADE, sprites=False, version=False)
        for args in (["--preview", "0"], ["--scope", "project", "--dir", d, "--dry-run"]):
            rc, said = _run(args, d, script=script)
            assert rc != 0 and install.NO_SPRITES in said, (args, said)
        rc, said = _run(["--version"], d, script=script)
        assert rc == 0 and said.strip() == "0.0.0", said


def test_굽기_칸_수_경계와_굽기_도구가_없을_때():
    with tempfile.TemporaryDirectory() as d:
        script = _copy(d, anim=MADE)
        path = _shim(d, has_numpy=True)
        rc, said = _run(["--bake", str(install.MIN_COLS - 1)], d, script=script, PATH=path)
        assert rc != 0 and f"{install.MIN_COLS}칸 이상" in said, said
        rc, said = _run(["--bake", str(install.MIN_COLS), "--dry-run"], d, script=script, PATH=path)
        assert rc == 0 and "(--dry-run 이라 굽지 않았다)" in said, said
        rc, said = _run(["--bake", "30"], d, script=script, PATH=_shim(os.path.join(d, "n"), has_numpy=False))
        assert rc != 0 and "numpy 와 pillow 가 필요하다" in said, said
        assert "ModuleNotFoundError" not in said, "확인용 파이썬의 오류를 그대로 흘렸다"
    for kwargs in ({"anim": None}, {"anim": MADE, "assets": False}):
        with tempfile.TemporaryDirectory() as d:
            script = _copy(d, **kwargs)
            rc, said = _run(["--bake", "30"], d, script=script, PATH=_shim(d, has_numpy=True))
            assert rc != 0 and "굽는 데 필요한 파일이 없다" in said, (kwargs, said)


def test_굽기가_성공하면_그_칸_수만_바꾸고_크기를_알려_준다():
    with tempfile.TemporaryDirectory() as d:
        script = _copy(d, anim=MADE)
        path = _shim(d, has_numpy=True)
        baked = os.path.join(d, ".claude", "plmi-sizes")
        os.makedirs(baked)
        for name in ("플밍이_숨쉬기_30x13.json", "플밍이_숨쉬기_40x15.json"):
            open(os.path.join(baked, name), "w").write("{}")
        for _ in range(2):
            rc, said = _run(["--bake", "30"], d, script=script, PATH=path)
            assert rc == 0 and "붙이려면 plmi --size 30x9\n" in said, said
        assert sorted(os.listdir(baked)) == ["플밍이_숨쉬기_30x9.json", "플밍이_숨쉬기_40x15.json",
                                             "플밍이_작업중_30x9.json"], os.listdir(baked)
    with tempfile.TemporaryDirectory() as d:
        script = _copy(d, anim="pass\n")
        baked = os.path.join(d, ".claude", "plmi-sizes")
        os.makedirs(baked)
        open(os.path.join(baked, "플밍이_숨쉬기_30x13.json"), "w").write("{}")
        rc, said = _run(["--bake", "30"], d, script=script, PATH=_shim(d, has_numpy=True))
        assert rc != 0 and "굽다가 멈췄다" in said, said
        assert os.listdir(baked) == ["플밍이_숨쉬기_30x13.json"], os.listdir(baked)


def test_새로_만든_설정_파일은_보통_권한이고_있던_파일은_권한과_한글을_지킨다():
    mask = os.umask(0)
    os.umask(mask)
    with tempfile.TemporaryDirectory() as d:
        ws = os.path.join(d, "ws")
        os.makedirs(ws)
        where = ["--scope", "project", "--dir", ws]
        assert _run(where, d)[0] == 0
        path = os.path.join(ws, ".claude", "settings.json")
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o666 & ~mask, oct(os.stat(path).st_mode)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"메모": "한글 값"}, f, ensure_ascii=False)
        os.chmod(path, 0o640)                          # mkstemp 가 만드는 0600 과 다른 권한으로 본다
        assert _run(where, d)[0] == 0
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o640, oct(os.stat(path).st_mode)
        with open(path, encoding="utf-8") as f:
            text = f.read()
        assert '"메모": "한글 값"' in text and '\n  "' in text, text


def test_설정_폴더를_만들_수_없으면_말하고_멈춘다():
    with tempfile.TemporaryDirectory() as d:
        ws = os.path.join(d, "ws")
        os.makedirs(ws)
        os.chmod(ws, 0o555)
        try:
            rc, said = _run(["--scope", "project", "--dir", ws], d)
        finally:
            os.chmod(ws, 0o755)
        assert rc != 0 and "설정 폴더를 만들 수 없다" in said, said


PURE = "PLMI_SIZE=16x8 sh -c 'exec python3 \"$0\" 2>/dev/null' /x/statusline.py"
ENVS = [
    ({"command": PURE}, {"PLMI_SIZE": "16x8"}),
    ({"command": "PLMI_BUBBLE=0 " + PURE}, {"PLMI_BUBBLE": "0", "PLMI_SIZE": "16x8"}),
    ({"command": "PLMI_SIZE=16x8 python3 /x/statusline.py"}, {"PLMI_SIZE": "16x8"}),
    ({"command": "PLMI_SIZE=16x8 python3 /x/statusline.py 더"}, None),
    ({"command": "PLMI_SIZE=16x8 python3 -u /x/statusline.py"}, None),
    ({"command": "PLMI_SIZE=16x8 env /x/statusline.py"}, None),
    ({"command": "PLMI_SIZE=16x8 bash -c 'exec python3 \"$0\" 2>/dev/null' /x/statusline.py"}, None),
    ({"command": PURE + " 더"}, None),
    ({"command": "PLMI_SIZE=16x8 sh -c 'echo 다른것' /x/statusline.py"}, None),
    ({"command": "python3 /x/statusline.py"}, None),
    ({"command": "PLMI_SIZE=16x8 python3 /x/other.py"}, None),
    ({"command": "PLMI_SIZE=16x8 echo '닫히지 않은"}, None),
    ({"command": "input=$(cat); echo \"$input\" | PLMI_SIZE=26x11 python3 /x/statusline.py; echo 다른것"}, None),
    ({"command": 3}, None),
    ("PLMI_SIZE=16x8 python3 /x/statusline.py", None),
    (None, None),
]


def test_플밍이만_부르는_명령인지_가르는_표():
    wrong = [(entry, install.plmi_env(entry), want) for entry, want in ENVS if install.plmi_env(entry) != want]
    assert not wrong, "\n".join(f"{e!r}: {g!r}, 기대 {w!r}" for e, g, w in wrong)
    for env in (None, {}, {"PLMI_BUBBLE": "0"}, {"PLMI_COLOR": "a b"}):
        line = install.command("26x11", env)
        assert install.plmi_env({"command": line}) == dict(env or {}, PLMI_SIZE="26x11"), line


def test_찾기가_훑는_범위():
    """홈 아래 네 단계와 Claude Code 가 기억하는 곳을 본다. 숨김 폴더는 안 훑고, 같은 곳은 한 번만 보인다."""
    with tempfile.TemporaryDirectory() as home:
        spots = {
            "top": os.path.join(home, "proj"),
            "deep4": os.path.join(home, "a", "b", "c", "d"),
            "deep5": os.path.join(home, "a", "b", "c", "d", "e"),
            "hidden": os.path.join(home, ".숨김", "ws"),
            "known": os.path.join(home, ".숨김", "기억", "ws"),
            "late": os.path.join(home, "zz", "ws"),
        }
        for ws in spots.values():
            os.makedirs(ws)
            assert _run(["--scope", "project", "--dir", ws], home)[0] == 0
        os.makedirs(os.path.join(home, "0broken", ".claude"))
        open(os.path.join(home, "0broken", ".claude", "settings.json"), "w").write("{깨짐")
        os.symlink(spots["top"], os.path.join(home, "링크"))
        with open(os.path.join(home, ".claude.json"), "w", encoding="utf-8") as f:
            json.dump({"projects": {spots["known"]: {}}}, f)
        rc, said = _run(["--where"], home)
        listed = [l for l in said.split("\n") if l.endswith("settings.json")]
        for name in ("top", "deep4", "known", "late"):
            assert any(l.startswith(spots[name]) for l in listed), f"{name} 를 못 찾았다: {said}"
        for name in ("deep5", "hidden"):
            assert not any(l.startswith(spots[name] + os.sep) for l in listed), f"{name} 까지 훑었다: {said}"
        assert len(listed) == len(set(os.path.realpath(l) for l in listed)), f"같은 곳을 두 번 보였다: {listed}"


def test_뗄_때_못_읽는_백업은_남기고_나머지를_치운다():
    with tempfile.TemporaryDirectory() as d:
        ws = os.path.join(d, "ws")
        os.makedirs(ws)
        where = ["--scope", "project", "--dir", ws]
        assert _run(where, d)[0] == 0
        room = os.path.join(ws, ".claude")
        open(os.path.join(room, "settings.json.bak_20000101_000000_plmi"), "w").write("{깨짐")
        with open(os.path.join(room, "settings.json.bak_20000101_000001_plmi"), "w") as f:
            json.dump({"statusLine": {"command": "echo 남의것"}}, f, ensure_ascii=False)
        with open(os.path.join(room, "settings.json.bak_20000101_000002_plmi"), "w") as f:
            json.dump({"statusLine": {"command": PURE}}, f)
        rc, said = _run(where + ["--uninstall"], d)
        assert rc == 0, said
        assert sorted(os.listdir(room)) == ["settings.json.bak_20000101_000000_plmi",
                                            "settings.json.bak_20000101_000001_plmi"], os.listdir(room)
        assert "남김" in said and "000001_plmi" in said, said
        assert "치움" in said and "000002_plmi" in said, said
