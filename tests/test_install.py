"""설치기가 남의 설정을 망가뜨리지 않는지."""
import json
import os
import re
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
        assert settings(d)["permissions"] == {"allow": ["Bash(ls:*)"]}


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
        run(d, "--force")
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
    """줄 수는 굽고 나서 정해진다. 기본값을 글자로 박아 두면 그때마다 없는 크기가 된다."""
    out = subprocess.run([sys.executable, INSTALL, "--help"],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    with tempfile.TemporaryDirectory() as d:
        assert run(d).returncode == 0
        size = settings(d)["statusLine"]["command"].split("PLMI_SIZE=")[1].split()[0]
    anim = os.path.join(grid.ROOT, "plmi", "sprites", "anim")
    hit = [f for f in os.listdir(anim) if f.endswith(f"_{size}.json")]
    assert hit, f"기본 크기 {size} 로 구운 스프라이트가 없다"


def test_버전을_말할_수_있다():
    """brew 가 깐 것과 저장소의 VERSION 이 같은지 사람이 확인할 길이 있어야 한다."""
    out = subprocess.run([sys.executable, INSTALL, "--version"],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    said = out.stdout.strip()
    with open(os.path.join(grid.ROOT, "VERSION"), encoding="utf-8") as f:
        assert said == f.read().strip(), f"--version 이 {said}"

def bare(*args, cwd=None, env=None):
    """--scope 를 붙이지 않고 그대로 부른다.

    HOME 을 임시 폴더로 돌린다. user 스코프가 기본이라 어딘가에서 그리로 흘러가면
    사람이 쓰는 홈의 settings.json 에 붙는다. 돌연변이는 소스를 되돌리지만 이렇게 남은
    파일은 안 되돌린다. 실제로 홈에 16x8 짜리가 붙어 다른 세션이 작게 나온 적이 있다.
    """
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
    """지목할 길이 없으면 워크스페이스마다 그 폴더로 옮겨 가야 한다.

    부른 자리가 아니라 지목한 자리에 붙는지를 본다. 그래서 둘을 갈라 둔다.
    """
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
        assert settings(d) is None


def test_붙인_자리를_찾아_준다():
    """떼려면 어디에 붙였는지 알아야 한다. 사람이 기억하고 있을 일이 아니다."""
    with tempfile.TemporaryDirectory() as home:
        work = os.path.join(home, "work", "myproj")
        os.makedirs(work)
        assert bare("--scope", "project", "--dir", work).returncode == 0
        out = bare("--where", env={"HOME": home})
        assert out.returncode == 0, out.stderr
        assert work in out.stdout, out.stdout
        assert "PLMI_SIZE" in out.stdout

        out = bare("--where", env={"HOME": os.path.join(home, "빈곳")})
        assert "붙어 있는 곳이 없다" in out.stdout

def test_남의_설정이_있으면_파일을_안_지운다():
    """치우는 것은 우리가 만든 빈 껍데기뿐이다."""
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, ".claude"))
        with open(os.path.join(d, ".claude", "settings.json"), "w", encoding="utf-8") as f:
            json.dump({"permissions": {"allow": ["Bash(ls:*)"]}}, f)
        run(d)
        run(d, "--uninstall")
        assert settings(d) == {"permissions": {"allow": ["Bash(ls:*)"]}}


def test_창보다_큰_크기는_막는다():
    """창보다 넓으면 줄바꿈으로 그림이 무너진다."""
    with tempfile.TemporaryDirectory() as d:
        big = max(grid.sizes(), key=lambda s: int(s.split("x")[0]))
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
    with tempfile.TemporaryDirectory() as d:
        out = bare("--preview", "0.2", "--size", grid.sizes()[-1],
                   "--scope", "project", "--dir", d, cwd=d)
        assert out.returncode == 0, out.stderr
        assert grid.sizes()[-1] in out.stdout, out.stdout
        # 미리 보기에만 있는 안내다. 이게 없으면 그냥 붙인 것이다
        assert "Ctrl+C" in out.stdout, out.stdout
        # 사람이 키보드로 치는 문자만 쓴다. em dash 는 쉼표나 마침표로 대신한다
        assert "\u2014" not in out.stdout, out.stdout
        assert settings(d) is None, "미리 보기가 설정을 건드렸다"


def test_떼는_순서를_안_지켜도_조용하다():
    """plmi --uninstall 없이 brew uninstall 을 하면 경로가 사라진다.

    Formula 에는 제거 훅이 없어(uninstall_preflight 는 Cask 전용) 순서를 강제할 수 없다.
    그때 파이썬이 뱉는 「No such file」이 상태줄 자리에 찍히면 안 된다.
    """
    with tempfile.TemporaryDirectory() as d:
        run(d)
        cmd = settings(d)["statusLine"]["command"]
        gone = cmd.replace(shlex.quote(runner(cmd)),
                           shlex.quote(os.path.join(d, "없어진", "statusline.py")))
        out = subprocess.run(gone, shell=True, input="{}",
                             capture_output=True, text=True, timeout=30)
        assert out.stdout.strip() == "", f"찍힌 것: {out.stdout[:80]!r}"
        # 감싸지 않으면 파이썬이 stderr 로 「No such file」을 뱉는다
        assert out.stderr.strip() == "", f"stderr: {out.stderr[:80]!r}"

def test_어느_사본이_붙였든_뗀다():
    """저장소에서 쓰던 것이나 옛 판이 붙인 것도 뗄 수 있어야 한다.

    경로로 거르면 홈에 남은 다른 사본의 설정을 --force 없이는 못 뗀다. 실제로 그래서
    손으로 지운 적이 있다.
    """
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, ".claude"))
        other = {"type": "command",
                 "command": "PLMI_SIZE=16x8 python3 /어딘가/다른사본/statusline.py"}
        with open(os.path.join(d, ".claude", "settings.json"), "w", encoding="utf-8") as f:
            json.dump({"statusLine": other}, f, ensure_ascii=False)
        assert run(d, "--uninstall").returncode == 0
        assert settings(d) is None


def test_다른_사본이_붙인_자리에_그냥_붙는다():
    """클론해 쓰던 사람이 brew 로 옮길 때 경로가 달라도 --force 를 알아야 하면 안 된다.

    막는 것은 플밍이가 아닌 상태줄뿐이다.
    """
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
    둘로 잘렸고, stderr 를 버리니 아무 표시 없이 비어 버렸다."""
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
