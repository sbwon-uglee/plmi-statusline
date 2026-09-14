"""굽는 쪽을 실제로 돌려 본다.

구운 파일만 검사하면 굽는 코드를 고쳐도 다시 굽기 전까지 아무것도 안 깨진다. 가장 작은 크기를
새로 구워 저장소의 스프라이트와 바이트까지 견준다. numpy 와 pillow 가 필요해서 없으면 건너뛴다.
"""
import glob
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile

import grid

ANIM = os.path.join(grid.ROOT, "plmi", "anim.py")


def baker():
    """numpy 와 pillow 로 파이썬을 부르는 명령 앞부분. 없으면 건너뛴다."""
    if shutil.which("uv"):
        cmd = ["uv", "run", "--no-project", "--offline", "--quiet", "--with", "numpy", "--with", "pillow", "python"]
        if subprocess.run(cmd + ["-c", "import numpy, PIL"], capture_output=True, timeout=120).returncode == 0:
            return cmd
    if subprocess.run([sys.executable, "-c", "import numpy, PIL"], capture_output=True).returncode == 0:
        return [sys.executable]
    raise grid.Skip("numpy 와 pillow 가 없다")


def _digest(paths):
    return {os.path.basename(p): hashlib.sha256(open(p, "rb").read()).hexdigest() for p in paths}


@grid.slow
def test_다시_구우면_저장소_스프라이트와_같다():
    cols = grid.sizes()[-1].split("x")[0]
    with tempfile.TemporaryDirectory() as d:
        out = subprocess.run(baker() + [ANIM, "--cols", cols, "--out", d],
                             capture_output=True, text=True, timeout=300)
        assert out.returncode == 0, out.stderr[-600:]
        made = _digest(glob.glob(os.path.join(d, "*.json")))
    kept = _digest(glob.glob(os.path.join(grid.ANIM, f"플밍이_*_{cols}x*.json")))
    assert made == kept, f"{cols}칸을 다시 구우니 다르다: {sorted(set(made.items()) ^ set(kept.items()))[:4]}"


@grid.slow
def test_build_sh_는_같은_칸_수를_두_번_줘도_스프라이트를_안_지운다():
    baker()
    with tempfile.TemporaryDirectory() as d:
        root = os.path.join(d, "repo")
        shutil.copytree(grid.ROOT, root, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        with open(os.path.join(root, "tests", "run.py"), "w", encoding="utf-8") as f:
            f.write("")                              # 굽기만 본다. 검사는 여기서 안 돌린다
        sprites = os.path.join(root, "plmi", "sprites", "anim")
        before = _digest(glob.glob(os.path.join(sprites, "*.json")))
        out = subprocess.run([os.path.join(root, "build.sh"), "16", "16"], capture_output=True, text=True,
                             timeout=300)
        assert out.returncode == 0, out.stderr[-400:]
        assert _digest(glob.glob(os.path.join(sprites, "*.json"))) == before, "같은 칸 수를 두 번 주니 스프라이트가 바뀌었다"


@grid.slow
def test_굽기가_실패하면_build_sh_가_스프라이트를_그대로_둔다():
    with tempfile.TemporaryDirectory() as d:
        root = os.path.join(d, "repo")
        shutil.copytree(grid.ROOT, root, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        sprites = glob.glob(os.path.join(root, "plmi", "sprites", "anim", "*.json"))
        before = _digest(sprites)
        out = subprocess.run([os.path.join(root, "build.sh"), "16", "abc"], capture_output=True, text=True,
                             timeout=300, env=dict(os.environ, TMPDIR=d))
        assert out.returncode != 0, "없는 칸 수인데 성공했다"
        after = _digest(glob.glob(os.path.join(root, "plmi", "sprites", "anim", "*.json")))
        assert after == before, "굽기가 멈췄는데 스프라이트가 바뀌었다"
        left = [n for n in os.listdir(d) if n != "repo"]
        assert not left, f"임시 폴더가 남았다: {left}"


@grid.slow
def test_설치기가_받는_가장_작은_칸_수도_스프라이트_규칙을_지킨다():
    """`plmi --bake` 로 받는 사람이 구운 것은 저장소 검사를 안 거친다. 받는 최소 칸 수로 구워 같은 규칙을 본다."""
    sys.path.insert(0, os.path.join(grid.ROOT, "plmi"))
    import install
    import test_sprites
    cols = str(install.MIN_COLS)
    with tempfile.TemporaryDirectory() as d:
        out = subprocess.run(baker() + [ANIM, "--cols", cols, "--out", d],
                             capture_output=True, text=True, timeout=300)
        assert out.returncode == 0, out.stderr[-600:]
        keep = grid.ANIM
        grid.ANIM = d
        try:
            for name in ("test_머리가_안_잘린다", "test_얼굴이_있다", "test_볼이_양쪽에_있다",
                         "test_볼이_눈이나_입과_안_겹친다", "test_아래에_빈_줄이_있다",
                         "test_파일이름의_줄수와_실제_줄수가_같다", "test_모든_크기에_여덟_상태가_있다"):
                try:
                    getattr(test_sprites, name)()
                except AssertionError as e:
                    raise AssertionError(f"{cols}칸: {name}: {e}")
        finally:
            grid.ANIM = keep
