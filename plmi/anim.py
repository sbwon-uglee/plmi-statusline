"""플밍이 애니메이션 프레임을 만들어 JSON 으로 남긴다.

원화가 두 장(미소·윙크)뿐이고 애니메이션은 미소 한 장으로 만든다. 원본2 는 배율을 정할 때만 쓴다. 떡 캐릭터라 스쿼시·스트레치가 가장
자연스럽다. 부피를 지키려고 가로와 세로를 반대로 움직이고, 눌릴 때는 바닥을 붙여 둔다.
눈은 원본에서 뜯어낸 덩어리를 따로 눌러 감음·반쯤·크게를 만든다.

    python terminal_char/anim.py                     프레임 생성
    python terminal_char/anim.py --squeeze 0.8       세로 눌림 바꿔 다시 생성
    python terminal_char/anim.py --cols 36 --rows 16 칸 수 바꿔 다시 생성
    python terminal_char/play.py 숨쉬기      터미널에서 재생
"""
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dot import Layout, face_art, fit, fit_color, headroom_scale, masks

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "assets")
OUT = os.path.join(HERE, "sprites", "anim")

FACES = {
    "미소": "plmi_smile.png",
    "윙크": "plmi_wink.png",
}
# 세로 눌림. 터미널 칸이 가로 1 세로 2 보다 길수록 낮춘다. 값 = 2 / (칸 세로 대 가로 비).
# 폰트 지표로 계산한 0.909 는 실제 화면에서 아직 길쭉해 보여 눈으로 맞춘 값을 쓴다.
SQUEEZE = 0.84
CW, CH = 26, 12          # 정지 그림보다 한 줄 넉넉하다. 늘어난 프레임이 들어갈 자리다

# 눈·입은 `dot.face_art` 가 점 격자에 직접 찍는다. 여기서는 어느 패턴을 쓸지만 고른다.
EYE = ["뜬눈", "반쯤", "감음", "크게", "기쁨", "뾰로통", "놀람", "뻗음", "찡그림", "일자"]

MOUTH = ["원본", "웃음", "크게웃음", "시무룩", "동그람", "일자", "삐죽"]


def breathe(n, depth, period=None, lift=0.0, sway=0, only=None):
    """사인 한 주기로 눌렀다 편다. 값은 (가로배율, 세로배율, 가로이동, 세로이동).

    only="squash" 면 기본 크기에서 눌리기만 한다. 늘어나는 쪽이 없으면 위로 비워 둘 자리도
    없어서, 깊게 누르는 상태도 캐릭터를 줄이지 않고 만들 수 있다.

    🔴누르기만 할 때 abs(sin) 을 쓰면 한 주기에 봉우리가 둘이라 뒤쪽 절반이 앞쪽 절반과
    글자까지 똑같은 그림이 된다(생각중 12장 중 서로 다른 것이 4장이었다). 봉우리가 하나인
    (1-cos)/2 로 바꾼다.

    🔴가로 흔들림은 위아래 움직임과 위상을 어긋나게 준다. 같은 위상이면 올라갈 때와
    내려갈 때가 거울처럼 겹쳐 서로 다른 그림이 반으로 준다. 누를 때는 sin, 늘일 때는
    cos 이 각각 그 대칭축에서 부호가 뒤집힌다.

    가로는 세로 변화의 0.6 만 따라간다. 부피를 그대로 지키면 깊게 누를 때 20% 넓어지고,
    그 최대폭에 맞춰 배율을 잡느라 캐릭터가 상시 작아진다.
    """
    WIDE = 0.6
    # 🔴점프는 줄 단위(4점)로만 준다. 반 줄(2점)이면 몸의 위 모서리가 줄 경계를 넘나들어
    # 차지하는 줄 수가 9→10→9 로 튀고, 자세는 매끈한데 그림이 덜컹거려 보인다.
    lift = round(lift / 4) * 4
    period = period or n
    out = []
    for i in range(n):
        a = 2 * math.pi * i / period
        if only == "squash":
            t = (1 - math.cos(a)) / 2
            out.append((1 + depth * t * WIDE, 1 - depth * t,
                        round(sway * math.sin(a)), 0))
            continue
        t = math.sin(a)
        out.append((1 - depth * t * WIDE, 1 + depth * t,
                    round(sway * math.cos(a)), -round(lift * max(0.0, t))))
    return out


# 한 장을 몇 초 보여줄지. statusline 은 쉴 때 초당 한 번뿐이라 대기 상태는 1초에 한 장씩
# 넘겨야 깜빡임이 깜빡임으로 보인다. 나머지는 비워 두면 한 바퀴 길이로 맞춘다.
HOLD = {"숨쉬기": 1.0}

# 캐릭터 아래에 비워 둘 줄. statusLine 바로 밑에 모드 표시줄이 붙어서, 발이 격자 맨
# 아랫줄까지 닿으면 그 줄과 맞닿아 보인다. 잘라내기가 끝난 뒤에 붙인다. 배율을 정할 때
# 끼워 넣으면 위쪽 여유를 그만큼 빼앗겨 캐릭터가 통째로 작아진다(26칸 10%, 16칸 27%).
MARGIN_BOTTOM = 1

PALETTE_N = 24
GAIN = 3.0                     # 칸 색 대비. 삼각면 진폭이 밝기 ±14 라 그대로 쓰면 무늬가 안 보인다.
                               # 평균을 축으로 벌려 준다
BLUSH = 2.0                    # 볼색을 원화 대비 몇 배로 진하게 할지. 원화 값 그대로(1.0)면
                               # 몸 색과 붙어 안 보이고, GAIN 을 그대로 받으면(3.0) 튄다
CHARS = "0123456789abcdefghijklmn"


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
    return cen, lab


def spec(poses, eyes, mouths="원본", face="미소"):
    """프레임마다 (자세, 눈, 입, 원화) 를 붙인다. 각 항목은 이름 하나 또는 프레임별 목록."""
    def spread(v):
        return [v] * len(poses) if isinstance(v, str) else v
    return list(zip(poses, spread(eyes), spread(mouths), spread(face)))


def blink_at(eyes, *frames):
    """지정한 프레임만 감았다 뜬다. 한 프레임만 감으면 너무 빨라 안 보인다."""
    out = list(eyes)
    for i in frames:
        for k, name in ((0, "반쯤"), (1, "감음"), (2, "감음"), (3, "반쯤")):
            if i + k < len(out):
                out[i + k] = name
    return out


def main():
    """⚠크기를 바꿔 다시 구울 때는 `sprites/anim/*.json` 을 먼저 지운다. 줄 수는 빈 줄을
    잘라낸 뒤 정해지므로 같은 `--rows` 로도 결과 이름이 달라질 수 있고, 옛 이름의 파일이
    남으면 그것을 보고 「안 바뀌었다」고 오판하게 된다."""
    global SQUEEZE, CH, CW
    if "--squeeze" in sys.argv:
        SQUEEZE = float(sys.argv[sys.argv.index("--squeeze") + 1])
    rows_given = "--rows" in sys.argv
    if rows_given:
        CH = int(sys.argv[sys.argv.index("--rows") + 1])
    if "--cols" in sys.argv:
        CW = int(sys.argv[sys.argv.index("--cols") + 1])
    global OUT
    if "--out" in sys.argv:
        # brew 로 깐 자리는 읽기 전용이고 판을 올리면 통째로 갈린다. 손수 굽는 것은
        # 홈 아래 쓸 수 있는 자리로 낸다
        OUT = os.path.abspath(os.path.expanduser(sys.argv[sys.argv.index("--out") + 1]))
    os.makedirs(OUT, exist_ok=True)
    M = {k: masks(os.path.join(SRC, v)) for k, v in FACES.items()}
    cache = {}
    lays = {}

    def layout(face, pose):
        """한 프레임의 기하를 한 번만 정하고 셋이 나눠 쓴다.

        전에는 face_art 와 fit 과 fit_color 에 칸 수와 배율과 자세를 따로따로 넘겼다. 인자가
        하나만 어긋나도 얼굴과 몸과 색이 다른 자리를 잡는데 그게 화면에서는 볼이
        흘러내린 것으로 보였다. 이제 어긋날 자리가 없다.
        """
        key = (face, pose)
        if key not in lays:
            sx, sy, dx, dy = pose
            lays[key] = Layout(M[face]["body"].shape, CW, CH, scale=scale,
                               squeeze=SQUEEZE, sx=sx, sy=sy, dx=dx, dy=dy)
        return lays[key]

    def variant(face, eye, mouth, pose=(1.0, 1.0, 0, 0)):
        # 점 격자에 찍으므로 자세마다 자리가 달라진다. 자세까지 열쇠에 넣는다.
        key = (face, eye, mouth, pose)
        if key not in cache:
            cache[key] = face_art(M[face], layout(face, pose), eye=eye, mouth=mouth)
        return cache[key]

    rest = breathe(14, 0.05, sway=1, only="squash")
    anims = {
        "숨쉬기": (1, spec(rest,
                        ["뜬눈"] * 3 + ["감음"] + ["뜬눈"] * 5
                        + ["감음"] + ["뜬눈"] * 4)),
        "작업중": (12, spec(breathe(12, 0.11, lift=4, sway=1), "뜬눈")),
        "생각중": (6, spec(breathe(12, 0.20, sway=1, only="squash"), "반쯤", "일자")),
        "승인대기": (8, spec(breathe(12, 0.05, sway=1),
                          blink_at(["크게"] * 12, 7), "동그람")),
        "완료": (8, spec(breathe(12, 0.09, lift=4, sway=1),
                       ["뜬눈"] * 2 + ["기쁨"] * 8 + ["뜬눈"] * 2,
                       ["원본"] * 2 + ["크게웃음"] * 8 + ["원본"] * 2)),
        "오류": (10, spec(breathe(8, 0.16, sway=1, only="squash"), "찡그림", "삐죽")),
        "놀람": (10, spec(breathe(10, 0.13, lift=4, sway=1), "놀람", "동그람")),
        # 눈은 평소대로 뜨고 입만 시무룩하다. 눈까지 찌푸리면 오래 띄워 둔 세션마다
        # 화난 얼굴이 되는데, 그건 오래 안 쓴 것이지 언짢은 것이 아니다
        "뾰로통": (6, spec(breathe(12, 0.08, sway=1), "뜬눈", "시무룩")),
    }

    poses_all = [p for _, sp in anims.values() for p, _, _, _ in sp]
    # 🔴줄 수는 잘리지 않을 만큼 넉넉히 잡는다. 늘 비는 줄은 뒤에서 잘라 내므로 넉넉해도
    # 손해가 없는데, 딱 맞게 잡으면 늘어나거나 뛰어오른 프레임을 받을 위쪽 여백이 없어
    # 배율이 확 줄고 캐릭터가 통째로 작아진다(20칸에서 배율이 42% 줄었다). 세로가 아니라
    # 가로가 배율을 정할 때까지 줄을 늘린다.
    if not rows_given:
        best, CH = 0.0, 4
        for ch in range(4, 4 * CW):
            s = headroom_scale(list(M.values()), poses_all, CW, ch, SQUEEZE)
            if s <= best * (1 + 1e-9):
                break
            best, CH = s, ch
    scale = headroom_scale(list(M.values()), poses_all, CW, CH, SQUEEZE)
    print(f"  {CW}칸 · 굽는 줄 {CH} · 배율 {scale:.4f}")

    cache.clear()
    lays.clear()

    # 색은 자세만 따라가므로 원화와 자세로만 뽑는다(눈·입 모양과 무관)
    # 색은 자세와 입 모양만 따라간다. 눈은 파낸 자리라 몸 색에 안 들어가고, 입은 그 둘레를
    # 물들이므로 모양이 바뀌면 물드는 칸도 바뀐다.
    tint = {}
    for name, (fps, sp) in anims.items():
        for (sx, sy, dx, dy), _, mouth, face in sp:
            key = (face, mouth, sx, sy, dx, dy)
            if key not in tint:
                tint[key] = fit_color(variant(face, "뜬눈", mouth, (sx, sy, dx, dy)),
                                      layout(face, (sx, sy, dx, dy)),
                                      gain=GAIN / BLUSH)
    body_mean = np.mean([c[v] for c, v in tint.values()][0], axis=0)
    for key, (col, cov) in tint.items():
        tint[key] = (np.clip(body_mean + (col - body_mean) * GAIN, 0, 255), cov)
    pool = np.concatenate([c[v] for c, v in tint.values()])
    # 볼 칸은 한 가지 색으로 딱 떨어지므로 팔레트 자리를 조금만 준다. 나머지는 몸통 결에 쓴다.
    warm = pool[:, 0] > pool[:, 1] - 20
    centers, _ = quantize(np.concatenate([pool] + [pool[warm]] * 2))

    def paint(key):
        col, cov = tint[key]
        d = ((col.reshape(-1, 1, 3) - centers[None, :, :]) ** 2).sum(2)
        lab = d.argmin(1).reshape(cov.shape)
        return ["".join(CHARS[i] if v else "." for i, v in zip(r, m))
                for r, m in zip(lab, cov)]

    built = {}
    for name, (fps, sp) in anims.items():
        built[name] = (fps,
                       [fit(variant(face, eye, mouth, (sx, sy, dx, dy)),
                            layout(face, (sx, sy, dx, dy)))
                        for (sx, sy, dx, dy), eye, mouth, face in sp],
                       ["\n".join(paint((face, mouth, sx, sy, dx, dy)))
                        for (sx, sy, dx, dy), _, mouth, face in sp])

    # 어느 상태의 어느 프레임에서도 안 쓰는 위아래 줄은 잘라 낸다. 뛰어오르는 프레임을 받으려고
    # 위에 여유를 두는데, 그 여유가 늘 비어 있으면 화면 줄만 차지한다.
    rows = range(CH)
    blank = [all(f.split("\n")[y].strip("⠀") == "" for _, fs, _ in built.values() for f in fs)
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
