"""설치기가 지켜야 하는 것들."""
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile

import grid

INSTALL = os.path.join(grid.ROOT, "plmi", "install.py")


def run(cwd, *args):
    return subprocess.run([sys.executable, INSTALL, "--scope", "project", *args],
                          cwd=cwd, capture_output=True, text=True, timeout=60)


def runner(cmd):
    """설정에 적힌 명령에서 statusline.py 경로만 뽑는다.

    명령은 셸로 감싸여 있고 경로는 셸 규칙대로 따옴표가 붙을 수 있다. 셸이 읽는 대로
    쪼개야 공백이 든 경로도 한 덩어리로 나온다.
    """
    for word in shlex.split(cmd):
        if word.endswith("statusline.py"):
            return word
    raise AssertionError(cmd)


def settings(cwd):
    p = os.path.join(cwd, ".claude", "settings.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def test_붙였다_뗀다():
    with tempfile.TemporaryDirectory() as d:
        assert run(d).returncode == 0
        s = settings(d)
        assert s["statusLine"]["type"] == "command"
        assert "statusline.py" in s["statusLine"]["command"]
        assert s["statusLine"]["refreshInterval"] == 1

        assert run(d, "--uninstall").returncode == 0
        # 우리가 만든 파일이면 뗄 때 같이 치운다. 빈 {} 가 워크스페이스마다 남지 않게
        assert settings(d) is None, "빈 껍데기가 남았다"


def test_다른_설정을_남긴다():
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, ".claude"))
        with open(os.path.join(d, ".claude", "settings.json"), "w", encoding="utf-8") as f:
            json.dump({"permissions": {"allow": ["Bash(ls:*)"]}}, f)
        run(d)
        assert settings(d)["permissions"] == {"allow": ["Bash(ls:*)"]}
        run(d, "--uninstall")
        # 치우는 것은 우리가 만든 빈 껍데기뿐이다
        assert settings(d) == {"permissions": {"allow": ["Bash(ls:*)"]}}


def test_남의_statusLine_을_안_덮는다():
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, ".claude"))
        theirs = {"type": "command", "command": "echo 남의것"}
        with open(os.path.join(d, ".claude", "settings.json"), "w", encoding="utf-8") as f:
            json.dump({"statusLine": theirs}, f, ensure_ascii=False)
        out = run(d)
        assert out.returncode != 0, "덮어써 버렸다"
        assert settings(d)["statusLine"] == theirs

        assert run(d, "--force").returncode == 0
        assert "statusline.py" in settings(d)["statusLine"]["command"]


def test_남의_statusLine_은_안_뗀다():
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, ".claude"))
        theirs = {"type": "command", "command": "echo 남의것"}
        with open(os.path.join(d, ".claude", "settings.json"), "w", encoding="utf-8") as f:
            json.dump({"statusLine": theirs}, f, ensure_ascii=False)
        assert run(d, "--uninstall").returncode != 0
        assert settings(d)["statusLine"] == theirs


def test_dry_run_은_안_쓴다():
    with tempfile.TemporaryDirectory() as d:
        assert run(d, "--dry-run").returncode == 0
        assert settings(d) is None


def test_쓰기_전에_백업한다():
    with tempfile.TemporaryDirectory() as d:
        run(d)
        run(d)
        backups = [f for f in os.listdir(os.path.join(d, ".claude")) if "bak_" in f]
        assert backups, "백업이 없다"


def test_절대경로를_쓴다():
    """받는 사람이 어느 폴더에서 Claude Code 를 띄우든 돌아야 한다."""
    with tempfile.TemporaryDirectory() as d:
        run(d)
        cmd = settings(d)["statusLine"]["command"]
        path = runner(cmd)
        assert os.path.isabs(path), cmd
        assert os.path.exists(path), path


def test_python3_을_PATH_에서_찾는다():
    """절대경로를 박으면 그 파이썬을 지웠을 때 statusLine 이 조용히 죽는다."""
    with tempfile.TemporaryDirectory() as d:
        run(d)
        assert " python3 " in settings(d)["statusLine"]["command"]


def test_brew_로_깔면_버전_없는_경로를_쓴다():
    """Cellar 경로를 적으면 다음 `brew upgrade` 가 그 폴더를 지워 상태줄이 조용히 죽는다.

    brew 는 `<prefix>/Cellar/<이름>/<버전>/` 에 두고 `<prefix>/opt/<이름>` 이 지금 버전을
    가리키게 한다. 설정에는 opt 쪽이 들어가야 버전을 올려도 산다.
    """
    with tempfile.TemporaryDirectory() as d:
        cellar = os.path.join(d, "Cellar", "plmi", "0.1.0", "libexec")
        os.makedirs(cellar)
        shutil.copytree(os.path.join(grid.ROOT, "plmi"), os.path.join(cellar, "plmi"))
        os.makedirs(os.path.join(d, "opt"))
        os.symlink(os.path.join(d, "Cellar", "plmi", "0.1.0"),
                   os.path.join(d, "opt", "plmi"))

        proj = os.path.join(d, "proj")
        os.makedirs(proj)
        out = subprocess.run(
            [sys.executable, os.path.join(cellar, "plmi", "install.py"),
             "--scope", "project"],
            cwd=proj, capture_output=True, text=True, timeout=60)
        assert out.returncode == 0, out.stderr
        cmd = settings(proj)["statusLine"]["command"]
        assert "/Cellar/" not in cmd, cmd
        assert os.path.join(d, "opt", "plmi") in cmd, cmd
        assert "0.1.0" not in cmd, f"경로에 버전이 박혔다: {cmd}"
        assert os.path.exists(runner(cmd)), cmd


def test_기본_크기가_실제로_있는_크기다():
    """기본 크기는 구워 둔 크기 중에서 고른다."""
    with tempfile.TemporaryDirectory() as d:
        assert run(d).returncode == 0
        size = settings(d)["statusLine"]["command"].split("PLMI_SIZE=")[1].split()[0]
    assert size in grid.sizes(), f"기본 크기 {size} 로 구운 스프라이트가 없다"


def test_버전을_말할_수_있다():
    """brew 가 깐 것과 저장소의 VERSION 이 같은지 사람이 확인할 길이 있어야 한다."""
    out = subprocess.run([sys.executable, INSTALL, "--version"],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    said = out.stdout.strip()
    with open(os.path.join(grid.ROOT, "VERSION"), encoding="utf-8") as f:
        assert said == f.read().strip(), f"--version 이 {said}"


def bare(*args, cwd=None, env=None):
    """인자를 그대로 넘기고 HOME 은 임시 폴더로 돌린다. 실제 홈 설정을 건드리지 않는다."""
    home = env.get("HOME") if env else None
    room = None
    if not home:
        room = tempfile.mkdtemp()
        home = room
    try:
        extra = dict(env or {})
        extra["HOME"] = home
        return subprocess.run([sys.executable, INSTALL, *args], cwd=cwd or grid.ROOT,
                              capture_output=True, text=True, timeout=60,
                              env=dict(os.environ, **extra))
    finally:
        if room:
            shutil.rmtree(room, ignore_errors=True)


def test_붙일_워크스페이스를_지목할_수_있다():
    """--dir 로 지목한 폴더에 붙고 부른 폴더에는 쓰지 않는다."""
    with tempfile.TemporaryDirectory() as here, tempfile.TemporaryDirectory() as there:
        out = bare("--scope", "project", "--dir", there, cwd=here)
        assert out.returncode == 0, out.stderr
        assert settings(there)["statusLine"]["type"] == "command"
        assert settings(here) is None, "부른 자리에 썼다"
        assert bare("--scope", "project", "--dir", there,
                    "--uninstall", cwd=here).returncode == 0
        assert settings(there) is None, "빈 껍데기가 남았다"


def test_지목한_폴더가_없으면_멈춘다():
    out = bare("--scope", "project", "--dir", "/없는/폴더")
    assert out.returncode != 0
    assert "없다" in out.stderr + out.stdout


def test_user_스코프에_폴더를_주면_멈춘다():
    """홈에 붙이는데 폴더를 받으면 어디에 쓸지 두 말이 된다."""
    with tempfile.TemporaryDirectory() as d:
        out = bare("--scope", "user", "--dir", d)
        assert out.returncode != 0


def test_붙인_자리를_찾아_준다():
    """떼려면 어디에 붙였는지 알아야 한다."""
    with tempfile.TemporaryDirectory() as home:
        work = os.path.join(home, "work", "myproj")
        os.makedirs(work)
        assert bare("--scope", "project", "--dir", work).returncode == 0
        out = bare("--where", env={"HOME": home})
        assert out.returncode == 0, out.stderr
        assert work in out.stdout, out.stdout
        assert "PLMI_SIZE" in out.stdout

        out = bare("--where", env={"HOME": os.path.join(home, "빈곳")})
        assert "못 찾았다" in out.stdout and "찾아본 곳" in out.stdout, out.stdout


def test_창보다_큰_크기는_막는다():
    """창보다 넓으면 줄바꿈으로 그림이 무너진다."""
    with tempfile.TemporaryDirectory() as d:
        big = grid.sizes()[0]
        out = subprocess.run([sys.executable, INSTALL, "--scope", "project",
                              "--dir", d, "--size", big],
                             capture_output=True, text=True, timeout=60,
                             env=dict(os.environ, COLUMNS="30", LINES="10"))
        assert out.returncode != 0, "좁은 창인데 통과했다"
        assert settings(d) is None
        # --force 면 사람이 알고 하는 것이라 통과시킨다
        out = subprocess.run([sys.executable, INSTALL, "--scope", "project",
                              "--dir", d, "--size", big, "--force"],
                             capture_output=True, text=True, timeout=60,
                             env=dict(os.environ, COLUMNS="30", LINES="10"))
        assert out.returncode == 0, out.stderr


def test_붙이지_않고_미리_볼_수_있다():
    """붙이지 않고 그 크기를 볼 수 있어야 크기를 고를 때 다시 띄우는 왕복이 없다."""
    small = grid.sizes()[-1]
    rows = int(small.split("x")[1])
    with tempfile.TemporaryDirectory() as d:
        out = bare("--preview", "1.5", "--state", "작업중", "--size", small,
                   "--scope", "project", "--dir", d, cwd=d)
        assert out.returncode == 0, out.stderr
        head, _, body = out.stdout.partition("\n")
        assert small in head, head
        assert body.startswith("\n" * rows + f"\x1b[{rows}A"), f"그 크기 줄 수만큼 자리를 비우고 올라가 그리지 않았다: {body[:40]!r}"
        frames = body.split(f"\x1b[{rows}A")[1:]
        assert 2 <= len(frames) <= 1.5 / 0.08 + 3, f"{len(frames)}장을 그렸다"
        assert all(f.count("\x1b[K\n") == rows for f in frames), "장마다 줄 수가 크기와 다르다"
        assert len(set(frames)) >= 2, "그림이 안 움직인다"
        # 미리 보기에만 있는 안내다. 이게 없으면 그냥 붙인 것이다
        assert "Ctrl+C" in out.stdout, out.stdout
        # 안내 문구에 em dash 를 안 쓴다
        assert "\u2014" not in out.stdout, out.stdout
        assert settings(d) is None, "미리 보기가 설정을 건드렸다"


def test_떼는_순서를_안_지켜도_조용하다():
    """plmi --uninstall 없이 brew uninstall 을 하면 경로가 사라진다. 그때 파이썬이 뱉는
    「No such file」이 상태줄 자리에 찍히면 안 된다.
    """
    with tempfile.TemporaryDirectory() as d:
        run(d)
        cmd = settings(d)["statusLine"]["command"]
        gone = cmd.replace(shlex.quote(runner(cmd)),
                           shlex.quote(os.path.join(d, "없어진", "statusline.py")))
        out = subprocess.run(gone, shell=True, input="{}",
                             capture_output=True, text=True, timeout=30)
        assert out.stdout.strip() == "", f"찍힌 것: {out.stdout[:80]!r}"
        assert out.stderr.strip() == "", f"stderr: {out.stderr[:80]!r}"


def test_어느_사본이_붙였든_뗀다():
    """경로가 다른 사본(클론, 다른 판)이 붙인 플밍이도 --force 없이 뗀다."""
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, ".claude"))
        other = {"type": "command",
                 "command": "PLMI_SIZE=16x8 python3 /어딘가/다른사본/statusline.py"}
        with open(os.path.join(d, ".claude", "settings.json"), "w", encoding="utf-8") as f:
            json.dump({"statusLine": other}, f, ensure_ascii=False)
        assert run(d, "--uninstall").returncode == 0
        assert settings(d) is None


def test_다른_사본이_붙인_자리에_그냥_붙는다():
    """다른 사본이 붙인 플밍이는 --force 없이 갈아 끼운다. 막는 것은 플밍이가 아닌 상태줄뿐이다."""
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, ".claude"))
        other = {"type": "command",
                 "command": "PLMI_SIZE=16x8 python3 /어딘가/다른사본/statusline.py"}
        with open(os.path.join(d, ".claude", "settings.json"), "w", encoding="utf-8") as f:
            json.dump({"statusLine": other}, f, ensure_ascii=False)
        out = run(d)
        assert out.returncode == 0, out.stderr
        assert "다른사본" not in settings(d)["statusLine"]["command"]


def test_공백이_든_경로에서도_돈다():
    """클론은 아무 데나 받는다. 「내 폴더」 처럼 공백이 든 자리에 받으면 명령 안에서 경로가
    둘로 잘리고, stderr 를 버리니 아무 표시 없이 빈다."""
    with tempfile.TemporaryDirectory() as base, tempfile.TemporaryDirectory() as d:
        room = os.path.join(base, "내 폴더")
        shutil.copytree(os.path.join(grid.ROOT, "plmi"), os.path.join(room, "plmi"))
        out = subprocess.run([sys.executable, os.path.join(room, "plmi", "install.py"),
                              "--scope", "project", "--dir", d],
                             capture_output=True, text=True, timeout=60)
        assert out.returncode == 0, out.stderr
        cmd = settings(d)["statusLine"]["command"]
        # 맥의 /var 는 /private/var 를 가리키는 링크라 실제 경로로 견준다
        assert (os.path.realpath(runner(cmd))
                == os.path.realpath(os.path.join(room, "plmi", "statusline.py"))), cmd
        shown = subprocess.run(cmd, shell=True, input="{}",
                               capture_output=True, text=True, timeout=30)
        rows = int(cmd.split("PLMI_SIZE=")[1].split()[0].split("x")[1])
        assert len(shown.stdout.rstrip("\n").split("\n")) == rows, f"{shown.stdout[:60]!r}"


def test_0초_미리보기와_0칸_굽기는_붙이지_않는다():
    """값이 0 이어도 미리 보기와 굽기로 다룬다. 거짓으로 읽으면 그냥 붙여 버린다."""
    with tempfile.TemporaryDirectory() as d:
        bare("--preview", "0", "--scope", "project", "--dir", d, cwd=d)
        assert settings(d) is None, "--preview 0 이 붙여 버렸다"
        out = bare("--bake", "0", "--scope", "project", "--dir", d, cwd=d)
        assert out.returncode != 0, out.stdout
        assert settings(d) is None, "--bake 0 이 붙여 버렸다"


def _theirs(d, command="echo 남의것"):
    os.makedirs(os.path.join(d, ".claude"), exist_ok=True)
    with open(os.path.join(d, ".claude", "settings.json"), "w", encoding="utf-8") as f:
        json.dump({"statusLine": {"type": "command", "command": command}}, f, ensure_ascii=False)


def _backed_up(d, command):
    """그 명령이 든 백업이 .claude 에 남아 있는지."""
    room = os.path.join(d, ".claude")
    for name in os.listdir(room) if os.path.isdir(room) else []:
        if "bak_" in name:
            with open(os.path.join(room, name), encoding="utf-8") as f:
                if command in f.read():
                    return True
    return False


def test_강제로_덮었다_떼도_원래_설정의_백업은_남는다():
    """--force 로 덮은 남의 statusLine 은 백업에만 남아 있다. 뗄 때 그 백업까지 치우면 되찾을 길이 없다."""
    with tempfile.TemporaryDirectory() as d:
        _theirs(d)
        assert run(d, "--force").returncode == 0
        assert run(d, "--uninstall").returncode == 0
        assert _backed_up(d, "echo 남의것"), "원래 설정이 든 백업이 지워졌다"


def test_남의_statusLine_을_강제로_떼면_백업을_남긴다():
    with tempfile.TemporaryDirectory() as d:
        _theirs(d)
        assert run(d, "--uninstall", "--force").returncode == 0
        assert _backed_up(d, "echo 남의것"), "뗀 statusLine 이 어디에도 없다"


def test_같은_초에_두_번_백업해도_앞_백업을_안_덮는다():
    code = (f"import sys; sys.path.insert(0, {os.path.join(grid.ROOT, 'plmi')!r})\n"
            "import install\n"
            "p = sys.argv[1]\n"
            "install.save(p, {'a': 1})\n"
            "install.save(p, {'a': 2})\n")
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, ".claude", "settings.json")
        os.makedirs(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"a": 0}\n')
        out = subprocess.run([sys.executable, "-c", code, path], capture_output=True, text=True, timeout=60)
        assert out.returncode == 0, out.stderr
        backups = [n for n in os.listdir(os.path.dirname(path)) if "bak_" in n]
        assert len(backups) == 2, backups


def test_statusline_py_가_없으면_알려_준다():
    with tempfile.TemporaryDirectory() as d:
        shutil.copytree(os.path.join(grid.ROOT, "plmi"), os.path.join(d, "plmi"))
        os.remove(os.path.join(d, "plmi", "statusline.py"))
        out = subprocess.run([sys.executable, os.path.join(d, "plmi", "install.py"), "--where"],
                             capture_output=True, text=True, timeout=60,
                             env=dict(os.environ, HOME=d))
        assert out.returncode != 0
        assert "못 찾았다" in out.stderr, out.stderr[-200:]


def test_settings_json_이_깨졌으면_손대지_않고_알려_준다():
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, ".claude"))
        path = os.path.join(d, ".claude", "settings.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write("{깨짐")
        out = run(d)
        assert out.returncode != 0
        assert "읽을 수 없다" in out.stderr, out.stderr[-200:]
        with open(path, encoding="utf-8") as f:
            assert f.read() == "{깨짐"


def test_창_크기는_말풍선_폭까지_센다():
    """말풍선은 그림 오른쪽에 붙는다. 그림만 들어가는 창에서도 말풍선이 줄바꿈되면 그림이 무너진다."""
    size = next(s for s in grid.sizes() if s.startswith("26x"))
    with tempfile.TemporaryDirectory() as d:
        narrow = dict(os.environ, COLUMNS="40", LINES="40")
        out = subprocess.run([sys.executable, INSTALL, "--scope", "project", "--dir", d, "--size", size],
                             capture_output=True, text=True, timeout=60, env=narrow)
        assert out.returncode != 0, "말풍선이 안 들어가는 창인데 통과했다"
        out = subprocess.run([sys.executable, INSTALL, "--scope", "project", "--dir", d, "--size", size],
                             capture_output=True, text=True, timeout=60, env=dict(narrow, PLMI_BUBBLE="0"))
        assert out.returncode == 0, out.stderr
        # 창 검사가 본 값이 명령에도 적혀야 실제 상태줄도 말풍선 없이 나온다
        assert "PLMI_BUBBLE=0" in settings(d)["statusLine"]["command"], settings(d)


def test_스프라이트가_없는_사본으로도_뗀다():
    """구운 파일이 빠진 사본으로도 붙어 있는 것을 뗀다."""
    with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as work:
        assert run(work).returncode == 0
        shutil.copytree(os.path.join(grid.ROOT, "plmi"), os.path.join(d, "plmi"),
                        ignore=shutil.ignore_patterns("anim"))
        out = subprocess.run([sys.executable, os.path.join(d, "plmi", "install.py"),
                              "--scope", "project", "--uninstall"],
                             cwd=work, capture_output=True, text=True, timeout=60,
                             env=dict(os.environ, HOME=d))
        assert out.returncode == 0, out.stderr
        assert settings(work) is None


def test_좁은_창이어도_남의_statusLine_을_먼저_알린다():
    """창 크기 안내만 보고 --force 를 붙이면 남의 statusLine 을 모르고 덮는다."""
    with tempfile.TemporaryDirectory() as d:
        _theirs(d)
        out = subprocess.run([sys.executable, INSTALL, "--scope", "project", "--dir", d],
                             capture_output=True, text=True, timeout=60,
                             env=dict(os.environ, COLUMNS="30", LINES="60"))
        assert out.returncode != 0 and "다른 statusLine" in out.stderr, out.stderr


def _fake_copy(d, anim_body):
    """굽기 스크립트를 바꿔 끼운 사본. 굽기가 실패하거나 성공하는 모양을 numpy 없이 만든다."""
    root = os.path.join(d, "copy")
    shutil.copytree(os.path.join(grid.ROOT, "plmi"), os.path.join(root, "plmi"),
                    ignore=shutil.ignore_patterns("__pycache__"))
    os.makedirs(os.path.join(root, "assets"))
    with open(os.path.join(root, "plmi", "anim.py"), "w", encoding="utf-8") as f:
        f.write(anim_body)
    return os.path.join(root, "plmi", "install.py")


MADE = """import os, sys
out = sys.argv[sys.argv.index("--out") + 1]
cols = sys.argv[sys.argv.index("--cols") + 1]
os.makedirs(out, exist_ok=True)
for s in ("숨쉬기", "작업중"):
    open(os.path.join(out, "플밍이_%s_%sx9.json" % (s, cols)), "w").write("{}")
"""


def test_굽기가_실패해도_전에_구운_크기는_남는다():
    with tempfile.TemporaryDirectory() as d:
        install = _fake_copy(d, "import sys\nsys.exit(1)\n")
        baked = os.path.join(d, "home", ".claude", "plmi-sizes")
        os.makedirs(baked)
        old = os.path.join(baked, "플밍이_숨쉬기_30x13.json")
        with open(old, "w") as f:
            f.write("{}")
        out = subprocess.run([sys.executable, install, "--bake", "30"], capture_output=True, text=True,
                             timeout=120, env=dict(os.environ, HOME=os.path.join(d, "home")))
        assert out.returncode != 0, out.stdout
        assert os.path.exists(old), "굽기가 멈췄는데 전에 구운 파일이 지워졌다"
        assert os.listdir(baked) == [os.path.basename(old)], os.listdir(baked)


def test_굽기에_dry_run_을_주면_굽지_않는다():
    with tempfile.TemporaryDirectory() as d:
        install = _fake_copy(d, MADE)
        home = os.path.join(d, "home")
        out = subprocess.run([sys.executable, install, "--bake", "30", "--dry-run"], capture_output=True,
                             text=True, timeout=120, env=dict(os.environ, HOME=home))
        assert out.returncode == 0 or "numpy" in out.stderr, out.stderr
        assert not os.path.exists(os.path.join(home, ".claude", "plmi-sizes")), "--dry-run 인데 구웠다"


def test_파이썬_프로젝트_폴더에서_구워도_그_폴더를_안_건드린다():
    if not shutil.which("uv"):
        raise grid.Skip("uv 가 없다")
    with tempfile.TemporaryDirectory() as d:
        install = _fake_copy(d, MADE)
        proj = os.path.join(d, "userproj")
        os.makedirs(proj)
        with open(os.path.join(proj, "pyproject.toml"), "w") as f:
            f.write('[project]\nname = "userproj"\nversion = "0.1.0"\nrequires-python = "==3.8.*"\n')
        out = subprocess.run([sys.executable, install, "--bake", "30"], cwd=proj, capture_output=True,
                             text=True, timeout=300, env=dict(os.environ, HOME=os.path.join(d, "home")))
        assert out.returncode == 0, out.stderr[-400:]
        assert sorted(os.listdir(proj)) == ["pyproject.toml"], os.listdir(proj)


def test_찾기는_Claude_Code_가_기억하는_깊은_워크스페이스도_보고_Library_는_안_훑는다():
    with tempfile.TemporaryDirectory() as home:
        deep = os.path.join(home, "a", "b", "c", "d", "e", "ws")
        hidden = os.path.join(home, "Library", "x", "ws")
        for ws in (deep, hidden):
            os.makedirs(ws)
            assert bare("--scope", "project", "--dir", ws).returncode == 0
        with open(os.path.join(home, ".claude.json"), "w", encoding="utf-8") as f:
            json.dump({"projects": {deep: {}}}, f)
        out = bare("--where", env={"HOME": home})
        assert deep in out.stdout, out.stdout
        assert hidden not in out.stdout, out.stdout
