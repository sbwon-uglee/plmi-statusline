"""받는 사람이 밟는 길을 처음부터 끝까지 따라간다.

brew 가 까는 모양(Cellar, opt 링크, bin/plmi 껍데기)을 임시 폴더에 만들고 붙이기, Claude Code 가
부르는 그대로 상태줄 명령 돌리기, 판 올리기, 크기 바꾸기, 떼기, brew 로 지우기를 이어서 본다.
클론으로 받는 길도 따라간다. 상태줄 명령은 PATH 의 python3 로 돌므로 파이썬마다 따로 돈다.
"""
import datetime
import json
import os
import shutil
import subprocess
import tempfile

import grid

# brew 포뮬러가 bin/plmi 로 쓰는 껍데기. 포뮬러를 고치면 여기도 같이 고친다
WRAPPER = '#!/bin/bash\nexec python3 "{libexec}/plmi/install.py" "$@"\n'


def _copy(dst, version):
    shutil.copytree(os.path.join(grid.ROOT, "plmi"), os.path.join(dst, "plmi"),
                    ignore=shutil.ignore_patterns("__pycache__", "state.json"))
    with open(os.path.join(dst, "VERSION"), "w", encoding="utf-8") as f:
        f.write(version + "\n")


def _brew(prefix, version):
    """Cellar 에 그 판을 깔고 opt 가 가리키게 한다."""
    keg = os.path.join(prefix, "Cellar", "plmi", version)
    _copy(os.path.join(keg, "libexec"), version)
    opt = os.path.join(prefix, "opt", "plmi")
    os.makedirs(os.path.dirname(opt), exist_ok=True)
    if os.path.lexists(opt):
        os.remove(opt)
    os.symlink(keg, opt)
    plmi = os.path.join(prefix, "bin", "plmi")
    os.makedirs(os.path.dirname(plmi), exist_ok=True)
    with open(plmi, "w", encoding="utf-8") as f:
        f.write(WRAPPER.format(libexec=os.path.join(opt, "libexec")))
    os.chmod(plmi, 0o755)
    return keg


def _env(d, home, python):
    shim = os.path.join(d, "shim")
    os.makedirs(shim, exist_ok=True)
    link = os.path.join(shim, "python3")
    if not os.path.lexists(link):
        os.symlink(python, link)
    path = os.pathsep.join([shim, os.path.join(d, "prefix", "bin"), "/usr/bin", "/bin"])
    return dict(os.environ, HOME=home, PATH=path, COLUMNS="200", LINES="60")


def _transcript(d):
    path = os.path.join(d, "t.jsonl")
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "assistant", "timestamp": now, "message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Read", "input": {"file_path": "/work/보고서.md"}}]}},
            ensure_ascii=False) + "\n")
    return path


def _settings(home):
    path = os.path.join(home, ".claude", "settings.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _claude(home, env, transcript):
    """Claude Code 처럼 설정의 명령을 셸로 부르고 세션 JSON 을 stdin 으로 준다."""
    cmd = _settings(home)["statusLine"]["command"]
    return subprocess.run(cmd, shell=True, input=json.dumps({"transcript_path": transcript}),
                          capture_output=True, text=True, timeout=30, env=env)


def _ok(cmd, env, cwd=None):
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env, cwd=cwd)
    assert out.returncode == 0, f"{cmd}: {out.stderr[-400:]}"
    return out.stdout


def _rows(out):
    return len(out.stdout.rstrip("\n").split("\n")) if out.stdout else 0


def test_brew_로_깔고_올리고_떼는_길():
    for python in grid.PYTHONS:
        with tempfile.TemporaryDirectory() as d:
            home = os.path.join(d, "home")
            os.makedirs(home)
            prefix = os.path.join(d, "prefix")
            env = _env(d, home, python)
            transcript = _transcript(d)
            who = f"[{python}]"

            old = _brew(prefix, "0.6.0")
            _ok(["plmi"], env)
            cmd = _settings(home)["statusLine"]["command"]
            assert os.path.join(prefix, "opt", "plmi") in cmd and "/Cellar/" not in cmd, f"{who} {cmd}"
            size = cmd.split("PLMI_SIZE=")[1].split()[0]
            shown = _claude(home, env, transcript)
            assert shown.stderr == "" and _rows(shown) == int(size.split("x")[1]), f"{who} {shown.stderr}"
            assert "읽는 중" in shown.stdout, f"{who} 말풍선이 없다"

            _brew(prefix, "0.7.0")
            shutil.rmtree(old)
            shown = _claude(home, env, transcript)
            assert _rows(shown) == int(size.split("x")[1]), f"{who} 판을 올리니 상태줄이 깨졌다: {shown.stderr}"
            assert _ok(["plmi", "--version"], env).strip() == "0.7.0", who

            small = grid.sizes()[-1]
            _ok(["plmi", "--size", small], env)
            assert _rows(_claude(home, env, transcript)) == int(small.split("x")[1]), f"{who} 크기를 바꿨는데 그대로다"

            _ok(["plmi", "--uninstall"], env)
            assert not os.path.exists(os.path.join(home, ".claude")), f"{who} 뗀 뒤 빈 껍데기가 남았다"

            _ok(["plmi"], env)
            shutil.rmtree(os.path.join(prefix, "Cellar"))
            os.remove(os.path.join(prefix, "opt", "plmi"))
            gone = _claude(home, env, transcript)
            assert gone.stdout == "" and gone.stderr == "", f"{who} brew 로 먼저 지웠더니 뭔가 찍힌다: {gone}"


def test_클론으로_받아_옮기고_다시_붙이는_길():
    for python in grid.PYTHONS:
        with tempfile.TemporaryDirectory() as d:
            home = os.path.join(d, "home")
            os.makedirs(home)
            env = _env(d, home, python)
            transcript = _transcript(d)
            who = f"[{python}]"

            first = os.path.join(d, "내 폴더 [2026]", "plmi-statusline")    # glob 이 특수 문자로 읽는 괄호
            _copy(first, "0.6.0")
            _ok(["python3", os.path.join(first, "plmi", "install.py")], env)
            assert "읽는 중" in _claude(home, env, transcript).stdout, who

            moved = os.path.join(d, "옮긴 곳", "plmi-statusline")
            os.makedirs(os.path.dirname(moved))
            shutil.move(first, moved)
            lost = _claude(home, env, transcript)
            assert lost.stdout == "" and lost.stderr == "", f"{who} 옮긴 뒤 뭔가 찍힌다"

            _ok(["python3", os.path.join(moved, "plmi", "install.py")], env)
            shown = _claude(home, env, transcript)
            assert "읽는 중" in shown.stdout, f"{who} 다시 붙였는데 안 나온다: {shown.stderr}"
            _ok(["python3", os.path.join(moved, "plmi", "install.py"), "--uninstall"], env)
            assert _settings(home) is None, who
