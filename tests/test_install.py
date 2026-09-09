"""설치기가 남의 설정을 망가뜨리지 않는지."""
import json
import os
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
