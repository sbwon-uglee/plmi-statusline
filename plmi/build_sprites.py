"""플밍이 스프라이트를 뽑아 파일로 남긴다.

원본 PNG 는 assets/ 에 있고 여기서는 읽기만 한다. 크기를 바꾸거나
표정이 늘면 이 스크립트를 다시 돌린다.

    python terminal_char/build_sprites.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dot import fit, masks, scale_for

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "assets")
OUT = os.path.join(HERE, "sprites")

FACES = {
    "미소": "plmi_smile.png",
    "윙크": "plmi_wink.png",
}
# 눈이 몸 너비의 5.6% 라 26칸(가로 52점) 아래로는 2.9점을 못 넘겨 파인 자리가 묻힌다.
# 줄 수는 몸 비율(가로 1.06)에 세로 눌림을 곱한 것이라 빈 줄이 남지 않는다.
# Ghostty 기본 폰트 JetBrains Mono 의 칸 비 2.2 를 상쇄한다 (2 / 2.2)
SQUEEZE = 0.909
SIZES = [(26, 11), (30, 13), (36, 16)]


def main():
    os.makedirs(OUT, exist_ok=True)
    paths = [os.path.join(SRC, fn) for fn in FACES.values()]
    made = []
    for cw, ch in SIZES:
        s = scale_for(paths, cw, ch, squeeze=SQUEEZE)
        for name, fn in FACES.items():
            art = fit(masks(os.path.join(SRC, fn)), cw, ch, scale=s, squeeze=SQUEEZE, texture=0)
            dst = os.path.join(OUT, f"플밍이_{name}_{cw}x{ch}.txt")
            with open(dst, "w", encoding="utf-8") as f:
                f.write(art + "\n")
            rows = art.split("\n")
            made.append((os.path.basename(dst), len(rows), max(len(r) for r in rows)))
    for n, rows, cols in made:
        print(f"  {n:<28} {rows}줄 x {cols}칸")
    print(f"\n{len(made)}개 · {OUT}")


if __name__ == "__main__":
    main()
