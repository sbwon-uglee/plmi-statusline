"""설치기가 남의 설정을 망가뜨리지 않는지."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import grid

INSTALL = os.path.join(grid.ROOT, "plmi", "install.py")


def run(cwd, *args):
    return subprocess.run([sys.executable, INSTALL, "--scope", "project", *args],
                          cwd=cwd, capture_output=True, text=True, timeout=60)


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
        assert "statusLine" not in settings(d)


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
        mine = {"type": "command", "command": "echo 남의것"}
        with open(os.path.join(d, ".claude", "settings.json"), "w", encoding="utf-8") as f:
            json.dump({"statusLine": mine}, f, ensure_ascii=False)
        out = run(d)
        assert out.returncode != 0, "덮어써 버렸다"
        assert settings(d)["statusLine"] == mine

        assert run(d, "--force").returncode == 0
        assert "statusline.py" in settings(d)["statusLine"]["command"]


def test_남의_statusLine_은_안_뗀다():
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, ".claude"))
        mine = {"type": "command", "command": "echo 남의것"}
        with open(os.path.join(d, ".claude", "settings.json"), "w", encoding="utf-8") as f:
            json.dump({"statusLine": mine}, f, ensure_ascii=False)
        assert run(d, "--uninstall").returncode != 0
        assert settings(d)["statusLine"] == mine


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
        path = cmd.split()[-1]
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
        assert os.path.exists(cmd.split()[-1]), cmd

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
