"""플밍이 애니메이션 프레임을 구워 JSON 으로 남긴다.

애니메이션은 미소 원화로 만들고 윙크 원화는 배율을 정할 때만 쓴다. 떡 캐릭터라 눌렀다
폈다 하며 움직인다. 가로와 세로를 반대로 움직이고, 눌릴 때는 바닥을 붙여 둔다.
눈과 입은 `dot.face_art` 가 점 패턴으로 찍는다.

    python3 plmi/anim.py                          26칸으로 굽는다
    python3 plmi/anim.py --cols 36                칸 수를 바꿔 굽는다. 줄 수는 알아서 잡는다
    python3 plmi/anim.py --cols 36 --rows 16      굽는 줄 수도 정한다. 파일 이름의 줄 수는 빈 줄을 잘라 낸 뒤 정해진다
    python3 plmi/anim.py --squeeze 0.8            세로 눌림을 바꾼다
    python3 plmi/anim.py --cols 30 --out <폴더>   다른 폴더로 굽는다
"""
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from dot import Layout, face_art, fit, fit_color, headroom_scale, masks

ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "assets")
OUT = os.path.join(HERE, "sprites", "anim")

FACES = {
    "미소": "plmi_smile.png",
    "윙크": "plmi_wink.png",
}
# 세로 눌림. 값 = 2 / (칸 세로 대 가로 비). 0.84 는 화면에서 눈으로 맞춘 값이다(폰트 지표로는 0.909).
SQUEEZE = 0.84
CW = 26                  # 칸 수 기본값


def breathe(n, depth, lift=0.0, sway=0, squash_only=False):
    """사인 한 주기로 눌렀다 편다. 값은 (가로배율, 세로배율, 가로이동, 세로이동).

    squash_only 면 늘어나지 않고 눌리기만 해서 위쪽 여백이 필요 없다. 눌림 값은 봉우리가
    하나인 (1-cos)/2 라 한 주기에 한 번 눌렸다 편다.
    가로 흔들림은 위아래 움직임과 위상을 어긋나게 준다. 가로는 세로 변화의 0.6 만 따라가
    가장 넓은 프레임 때문에 배율이 줄지 않게 한다.
    """
    WIDE = 0.6
    # 점프 꼭대기 높이를 줄 단위(4점)로 맞춘다
    lift = round(lift / 4) * 4
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n
        if squash_only:
            t = (1 - math.cos(a)) / 2
            out.append((1 + depth * t * WIDE, 1 - depth * t,
                        round(sway * math.sin(a)), 0))
            continue
        t = math.sin(a)
        out.append((1 - depth * t * WIDE, 1 + depth * t,
                    round(sway * math.cos(a)), -round(lift * max(0.0, t))))
    return out


# 한 장을 보여 줄 초. 쉴 때 statusline 이 초당 한 번 불리므로 숨쉬기는 1초에 한 장씩 넘긴다.
# 여기 없는 상태는 statusline 의 CYCLE 초에 한 바퀴 돈다.
HOLD = {"숨쉬기": 1.0}

# 캐릭터 아래에 비워 둘 줄. 발이 statusLine 바로 밑 모드 표시줄과 맞닿지 않게 한다.
# 배율에 영향이 없도록 빈 줄을 잘라 낸 뒤에 붙인다.
MARGIN_BOTTOM = 1

CHARS = "0123456789abcdefghijklmn"
PALETTE_N = len(CHARS)         # 색 번호를 CHARS 한 글자로 적는다
GAIN = 3.0                     # 칸 색 대비. 삼각면 진폭이 밝기 ±14 라 그대로 쓰면 무늬가 안 보인다.
                               # 평균을 축으로 벌려 준다
BLUSH = 2.0                    # 볼색이 몸 평균에서 떨어진 거리를 원화의 몇 배로 할지


def quantize(cells, n=PALETTE_N, rounds=12):
    """칸 색을 n 개로 줄인다. 색 escape 를 매 칸 찍지 않으려면 색 가짓수가 적어야 한다."""
    x = cells.reshape(-1, 3)
    idx = np.linspace(0, len(x) - 1, n).astype(int)
    cen = x[np.argsort(x[:, 1])][idx].astype(np.float64)
    for _ in range(rounds):
        d = ((x[:, None, :] - cen[None, :, :]) ** 2).sum(2)
        lab = d.argmin(1)
        for k in range(n):
            if (lab == k).any():
                cen[k] = x[lab == k].mean(0)
    return cen


def spec(poses, eyes, mouths="미소"):
    """프레임마다 (자세, 눈, 입) 을 붙인다. 눈과 입은 이름 하나 또는 프레임별 목록."""
    def spread(v):
        return [v] * len(poses) if isinstance(v, str) else v
    return list(zip(poses, spread(eyes), spread(mouths)))


def blink_at(eyes, *frames):
    """지정한 프레임부터 네 장에 걸쳐 반쯤, 감음, 감음, 반쯤으로 감았다 뜬다."""
    out = list(eyes)
    for i in frames:
        for k, name in ((0, "반쯤"), (1, "감음"), (2, "감음"), (3, "반쯤")):
            if i + k < len(out):
                out[i + k] = name
    return out


def main():
    """직접 부를 때는 같은 칸 수의 옛 파일(`플밍이_*_<칸>x*.json`)을 먼저 지운다. 파일 이름의
    줄 수는 굽고 나서 정해진다."""
    global SQUEEZE, CW, OUT
    if "--squeeze" in sys.argv:
        SQUEEZE = float(sys.argv[sys.argv.index("--squeeze") + 1])
    rows_given = "--rows" in sys.argv
    if rows_given:
        CH = int(sys.argv[sys.argv.index("--rows") + 1])
    if "--cols" in sys.argv:
        CW = int(sys.argv[sys.argv.index("--cols") + 1])
    if "--out" in sys.argv:
        # install.py 의 --bake 가 홈 아래 폴더를 준다
        OUT = os.path.abspath(os.path.expanduser(sys.argv[sys.argv.index("--out") + 1]))
    os.makedirs(OUT, exist_ok=True)
    M = {k: masks(os.path.join(SRC, v)) for k, v in FACES.items()}
    art = M["미소"]
    cache = {}
    lays = {}

    def layout(pose):
        """자세마다 Layout 을 하나 만들어 face_art, fit, fit_color 가 같이 쓴다."""
        if pose not in lays:
            sx, sy, dx, dy = pose
            lays[pose] = Layout(art["body"].shape, CW, CH, scale=scale,
                                squeeze=SQUEEZE, sx=sx, sy=sy, dx=dx, dy=dy)
        return lays[pose]

    def variant(eye, mouth, pose):
        # 점 격자에 찍으므로 자세마다 자리가 달라진다. 자세까지 열쇠에 넣는다.
        key = (eye, mouth, pose)
        if key not in cache:
            cache[key] = face_art(art, layout(pose), eye=eye, mouth=mouth)
        return cache[key]

    rest = breathe(14, 0.05, sway=1, squash_only=True)
    anims = {
        "숨쉬기": (1, spec(rest,
                        ["뜬눈"] * 3 + ["감음"] + ["뜬눈"] * 5
                        + ["감음"] + ["뜬눈"] * 4)),
        "작업중": (12, spec(breathe(12, 0.11, lift=4, sway=1), "뜬눈")),
        "생각중": (6, spec(breathe(12, 0.20, sway=1, squash_only=True), "반쯤", "일자")),
        "승인대기": (8, spec(breathe(12, 0.05, sway=1),
                          blink_at(["크게"] * 12, 7), "동그람")),
        "완료": (8, spec(breathe(12, 0.09, lift=4, sway=1),
                       ["뜬눈"] * 2 + ["기쁨"] * 8 + ["뜬눈"] * 2,
                       ["미소"] * 2 + ["크게웃음"] * 8 + ["미소"] * 2)),
        "오류": (10, spec(breathe(8, 0.16, sway=1, squash_only=True), "찡그림", "삐죽")),
        "놀람": (10, spec(breathe(10, 0.13, lift=4, sway=1), "놀람", "동그람")),
        # 오래 쉰 상태라 눈은 뜨고 입만 시무룩하다
        "뾰로통": (6, spec(breathe(12, 0.08, sway=1), "뜬눈", "시무룩")),
    }

    poses_all = [p for _, sp in anims.values() for p, _, _ in sp]
    # --rows 가 없으면 배율이 더 커지지 않을 때까지 줄을 늘린다. 늘 비는 줄은 뒤에서 잘라 낸다
    if not rows_given:
        best, CH = 0.0, 4
        for ch in range(4, 4 * CW):
            s = headroom_scale(list(M.values()), poses_all, CW, ch, SQUEEZE)
            if s <= best * (1 + 1e-9):
                break
            best, CH = s, ch
    scale = headroom_scale(list(M.values()), poses_all, CW, CH, SQUEEZE)
    print(f"  {CW}칸 · 굽는 줄 {CH} · 배율 {scale:.4f}")

    # 색은 자세와 입 모양으로 뽑는다. 눈 모양마다 따로 뽑지 않고 뜬눈으로 계산한다
    tint = {}
    for name, (fps, sp) in anims.items():
        for pose, _, mouth in sp:
            key = (mouth, pose)
            if key not in tint:
                tint[key] = fit_color(variant("뜬눈", mouth, pose), layout(pose),
                                      gain=GAIN / BLUSH)
    # 첫 색 한 장의 몸 평균을 축으로 대비를 벌린다
    col0, cov0 = next(iter(tint.values()))
    body_mean = np.mean(col0[cov0], axis=0)
    for key, (col, cov) in tint.items():
        tint[key] = (np.clip(body_mean + (col - body_mean) * GAIN, 0, 255), cov)
    pool = np.concatenate([c[v] for c, v in tint.values()])
    # 빨강이 초록보다 20 넘게 낮지 않은 칸(볼과 노란 면)은 세 번 넣어 팔레트 자리를 더 준다
    warm = pool[:, 0] > pool[:, 1] - 20
    centers = quantize(np.concatenate([pool] + [pool[warm]] * 2))

    def paint(key):
        col, cov = tint[key]
        d = ((col.reshape(-1, 1, 3) - centers[None, :, :]) ** 2).sum(2)
        lab = d.argmin(1).reshape(cov.shape)
        return ["".join(CHARS[i] if v else "." for i, v in zip(r, m))
                for r, m in zip(lab, cov)]

    built = {}
    for name, (fps, sp) in anims.items():
        built[name] = (fps,
                       [fit(variant(eye, mouth, pose), layout(pose)) for pose, eye, mouth in sp],
                       ["\n".join(paint((mouth, pose))) for pose, _, mouth in sp])

    # 어느 상태의 어느 프레임에서도 안 쓰는 위아래 줄은 잘라 낸다. 뛰어오르는 프레임을 받으려고
    # 위에 여유를 두는데, 그 여유가 늘 비어 있으면 화면 줄만 차지한다.
    rows = range(CH)
    blank = [all(f.split("\n")[y].strip("\u2800") == "" for _, fs, _ in built.values() for f in fs)
             for y in rows]
    lo = next((y for y in rows if not blank[y]), 0)
    hi = next((y for y in reversed(rows) if not blank[y]), CH - 1) + 1
    ch_out = hi - lo + MARGIN_BOTTOM
    gap_art = ["\u2800" * CW] * MARGIN_BOTTOM
    gap_tint = ["." * CW] * MARGIN_BOTTOM

    for name, (fps, frames, tints) in built.items():
        frames = ["\n".join(f.split("\n")[lo:hi] + gap_art) for f in frames]
        tints = ["\n".join(t.split("\n")[lo:hi] + gap_tint) for t in tints]
        dst = os.path.join(OUT, f"플밍이_{name}_{CW}x{ch_out}.json")
        with open(dst, "w", encoding="utf-8") as f:
            json.dump({"cw": CW, "ch": ch_out, "fps": fps, "hold": HOLD.get(name),
                       "frames": frames,
                       "tints": tints,
                       "palette": [[int(v) for v in c] for c in centers]},
                      f, ensure_ascii=False)
        print(f"  {os.path.basename(dst):<30} {len(frames)}프레임"
              f"(다른 그림 {len(set(frames))}) {fps}fps"
              f" · {len(frames) / fps:.1f}초")
    print(f"\n{OUT}")


if __name__ == "__main__":
    main()
