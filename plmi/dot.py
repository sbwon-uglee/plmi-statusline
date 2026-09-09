"""플밍이 원화를 브라유 점 격자로 옮긴다.

몸통은 통째로 채우고, 눈·입은 통째로 파낸다. 점묘(`--dither`)도
남겨 뒀으나 플밍이는 몸통이 거의 균일한 연민트라 디더링을 걸면 원본에 없던 직조 무늬가
생겨 캐릭터를 덜 닮는다.

읽히는 데 걸리는 것 여섯 가지.

1. 원본 1번은 오른쪽 아래로 그림자가 깔려 있고 몸 가장자리가 그 그림자와 섞여 어둡다.
   어두운 픽셀을 그대로 얼굴로 보면 테두리가 통째로 파인다. 몸을 조금 깎아낸 안쪽에서만
   얼굴을 찾는다.
2. 볼터치는 주황이고 눈·입은 초록 계열이라 색으로 갈린다. 볼은 폭이 몸의 11.9% 로 눈보다
   두 배 넓어, 눈·입과 같은 무게로 파면 얼굴을 잡아먹는다. 한 칸 걸러 파서 옅은 톤으로 둔다.
3. 미소의 입은 밝은 초록선이라 밝기 180 이다. 고정 문턱 150 으로는 얼굴에 안 잡혀 통째로
   빠진다. 몸통 중앙값(229)의 0.85 배를 문턱으로 쓴다. 획 두께도 몸 너비의 2.9% 라 26칸에서
   1.4점뿐이니, 면적 평균으로 줄이고 낮은 문턱을 써야 안정적으로 남는다.
4. 브라유 한 칸은 가로 2점 세로 4점, 터미널 칸은 가로 1 세로 2 라 점 하나가 정사각이다.
   원본 비율을 점 개수로 그대로 옮기면 된다.
5. 몸통 텍스처는 들로네 삼각형이다(면적 중앙 1,093px · 한 변 약 47px · 몸 너비의 3.4%).
   26칸에서 한 변이 1.6점이라 파낸 자리가 면으로 안 읽히고 얽은 자국이 된다. 그래서 기본은
   끔이다. `--texture <백분위>` 로 켤 수는 있고, 켤 때는 면을 한 값으로 눕힌 뒤 줄여야
   직선 경계가 남는다.
6. 터미널 칸이 가로 1 세로 2 보다 길면 점도 세로로 늘어져 캐릭터가 홀쭉해 보인다.
   `squeeze` 로 세로를 미리 줄인다. 값 = 2 / (칸 세로 대 가로 비). 기본 0.909 는 Ghostty
   기본 폰트 JetBrains Mono 기준이다(자간 600/1000 em, 줄 1020+300 = 1320/1000 em,
   칸 비 2.2). 다른 폰트를 쓰면 이 값을 바꾼다.

    python terminal_char/dot.py <원본.png> [칸너비] [칸높이] [--texture 백분위] [--squeeze 값]
    python terminal_char/dot.py <원본.png> [칸너비] [칸높이] [몸통밀도] --dither
"""
import sys

from collections import deque

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from sprite import braille


def bayer(n=8):
    m = np.array([[0]])
    while m.shape[0] < n:
        m = np.block([[4 * m, 4 * m + 2], [4 * m + 3, 4 * m + 1]])
    return (m + 0.5) / m.size


def dots(path, cw=26, ch=13, body=0.72, ring=2, gain=0.20, pad=0.04, mat=8,
         face=0.0, outline=True):
    """밝기를 정렬 디더로 옮긴다. Floyd-Steinberg 는 균일한 면에 사선 해칭을 만든다."""
    im = Image.open(path).convert("RGBA")
    im = im.crop(im.split()[3].getbbox())
    a = np.asarray(im).astype(np.float64)
    rgb, al = a[..., :3], a[..., 3] / 255.0
    lum = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    chroma = rgb.max(2) - rgb.min(2)
    dark = (al > 0.5) & (lum < 150) & (chroma >= 40)
    w, h = im.size
    m = int(max(w, h) * pad)

    def pack(arr):
        c = Image.new("L", (w + 2 * m, h + 2 * m), 0)
        c.paste(Image.fromarray(arr.astype(np.uint8)), (m, m))
        return c.resize((cw * 2, ch * 4), Image.LANCZOS)

    A = np.asarray(pack(al * 255)).astype(np.float64) / 255.0
    L = np.asarray(pack(lum)).astype(np.float64)
    Dim = pack(dark * 255)
    D = np.asarray(Dim) > 60

    inside = A > 0.5
    v = np.zeros(L.shape)
    t = 1 - (L[inside] - L[inside].min()) / max(1e-6, float(np.ptp(L[inside])))
    v[inside] = np.clip(body + gain * (t - t.mean()), 0, 1)
    if outline:
        inner = np.asarray(Image.fromarray((inside * 255).astype(np.uint8))
                           .filter(ImageFilter.MinFilter(3))) > 127
        v[inside & ~inner] = 1.0
    if ring:
        fat = np.asarray(Dim.filter(ImageFilter.MaxFilter(2 * ring + 1))) > 60
        v[fat & ~D] = 1.0
    v[D] = face

    th = bayer(mat)
    H, W = v.shape
    th = np.tile(th, (H // th.shape[0] + 1, W // th.shape[1] + 1))[:H, :W]
    return braille(["".join("#" if p else "." for p in r) for r in (v > th)])


def masks(path, rim=0.02, drop=0.85, warm=10, hipass=24):
    """몸통·얼굴·볼터치 마스크와 결정면 고주파를 뽑아 몸통 bbox 로 자른다.

    rim 은 얼굴을 찾지 않을 가장자리 두께(긴 변 대비), drop 은 몸통 중앙값 대비 얼굴로 볼
    밝기 비율, warm 은 볼터치로 볼 적색 우세폭이다. 큰 커널 MinFilter 는 O(k^2) 라 8분의 1로
    줄인 마스크에서 깎는다.
    """
    a = np.asarray(Image.open(path).convert("RGBA")).astype(np.float64)
    rgb, al = a[..., :3], a[..., 3]
    lum = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    body = al > 127
    h, w = body.shape

    sm = Image.fromarray((body * 255).astype(np.uint8)).resize((w // 8, h // 8), Image.BILINEAR)
    k = 2 * max(1, round(max(w, h) * rim / 8)) + 1
    inner = np.asarray(sm.filter(ImageFilter.MinFilter(k)).resize((w, h), Image.BILINEAR)) > 127

    med = float(np.median(lum[body]))
    face = inner & (lum < med * drop) & (rgb[..., 1] >= rgb[..., 0])
    blush = inner & (rgb[..., 0] > rgb[..., 1] + warm) & ~face

    blur = np.asarray(Image.fromarray(np.clip(lum, 0, 255).astype(np.uint8))
                      .filter(ImageFilter.GaussianBlur(hipass))).astype(np.float64)
    hp = lum - blur

    # 삼각면 하나를 한 값으로 눕힌다. 원본은 들로네 삼각형마다 그라데이션이 들어 있어
    # 고주파를 그대로 줄이면 삼각형 경계가 뭉개지고 둥근 얼룩이 남는다. 거칠게 양자화한 뒤
    # 최빈값 필터를 세 번 걸면 면 안쪽은 평평해지고 직선 경계는 남는다.
    im = Image.fromarray(np.clip(128 + hp * 8, 0, 255).astype(np.uint8))
    for k in (5, 9, 9):
        im = im.filter(ImageFilter.ModeFilter(k))
    facet = (np.asarray(im).astype(np.float64) - 128) / 8

    ys, xs = np.nonzero(body)
    box = (slice(ys.min(), ys.max() + 1), slice(xs.min(), xs.max() + 1))
    out = {k2: v[box] for k2, v in
           {"body": body, "face": face, "blush": blush, "inner": inner,
            "hp": hp, "facet": facet}.items()}
    out["rgb"] = rgb[box]              # 칸 색을 뽑을 때 쓴다
    # 🔴표정을 바꿔도 원화 눈·입이 있던 자리는 색 계산에서 늘 뺀다. 새 모양이 원화보다
    # 작으면 안 덮인 자리가 몸통으로 세어지는데, 눈 안쪽 밝기가 85 라 몸통 228 을 끌어
    # 내리고 GAIN 이 그 차를 세 배로 벌려 눈 옆 칸 하나가 올리브색 얼룩이 된다.
    # 실측 = 감음 막대는 원화 눈·입의 32%, 윙크 19%, 뜬눈조차 1.1% 가 안 덮인다.
    out["face0"] = out["face"]
    # 입은 점을 파내서 만들어 그 자리에 색을 실을 수 없다. 파낸 자리 둘레를 물들이려고
    # 원화에서 입 색을 재 둔다(원본1 = 159,199,139 · 원본2 = 99,187,59).
    mouth = split_face(out)[1]
    if mouth is not None:
        out["mouth_rgb"] = out["rgb"][mouth[:, 0], mouth[:, 1]].mean(axis=0)
    return out


class Layout:
    """원화를 점 격자 어디에 얼마로 앉힐지 한 곳에서 정한다.

    `fit`, `face_art`, `fit_color` 가 같은 여덟 줄을 각자 세우고 있었다. 한 곳만 고치면
    나머지 둘이 다른 자리를 잡아 볼이 입에서 떨어지고 눈 옆에 얼룩이 남았다. 셋이 이
    객체를 나눠 받으면 어긋날 자리가 없다.

    좌표계가 둘이다. 원화 픽셀 `(h, w)` 와 점 격자 `(H, W)`. `tw0`·`th0` 는 자세를 주기
    전 기준 크기, `tw`·`th` 는 자세를 준 뒤 크기다. **자리는 기준 크기로 잡고 크기만
    자세로 준다.** 눌린 프레임이 바닥을 붙인 채 위로만 줄어야 떡이 공중에 뜨지 않는다.
    """

    __slots__ = ("h", "w", "cw", "ch", "W", "H", "pad", "squeeze", "scale",
                 "tw0", "th0", "tw", "th", "ox", "oy")

    def __init__(self, shape, cw, ch, scale=None, pad=1, squeeze=0.909,
                 sx=1.0, sy=1.0, dx=0, dy=0):
        self.h, self.w = shape
        self.cw, self.ch = cw, ch
        self.W, self.H = cw * 2, ch * 4
        self.pad, self.squeeze = pad, squeeze
        self.scale = self.fill(shape, cw, ch, pad, squeeze) if scale is None else scale
        self.tw0 = max(1, round(self.w * self.scale))
        self.th0 = max(1, round(self.h * self.scale * squeeze))
        self.tw = max(1, round(self.tw0 * sx))
        self.th = max(1, round(self.th0 * sy))
        self.ox = (self.W - self.tw0) // 2 + (self.tw0 - self.tw) // 2 + dx
        self.oy = (self.H - self.th0) // 2 + (self.th0 - self.th) + dy

    @staticmethod
    def fill(shape, cw, ch, pad=1, squeeze=0.909):
        """자세를 안 준 그림이 격자를 꽉 채우는 배율."""
        h, w = shape
        return min((cw * 2 - 2 * pad) / w, (ch * 4 - 2 * pad) / (h * squeeze))

    def to_src(self, r0, c0, ry, rx):
        """격자 점 한 칸이 덮는 원화 픽셀 범위 (y0, y1, x0, x1)."""
        y0 = max(0, int(np.ceil((r0 + ry - self.oy) * self.h / self.th)))
        y1 = min(self.h, int(np.floor((r0 + ry + 1 - self.oy) * self.h / self.th)))
        x0 = max(0, int(np.ceil((c0 + rx - self.ox) * self.w / self.tw)))
        x1 = min(self.w, int(np.floor((c0 + rx + 1 - self.ox) * self.w / self.tw)))
        return y0, y1, x0, x1

    def row(self, src_y):
        """원화 세로 좌표를 격자 점 줄로."""
        return self.oy + src_y * self.th / self.h

    def col(self, src_x):
        """원화 가로 좌표를 격자 점 칸으로."""
        return self.ox + src_x * self.tw / self.w


def fit(m, lay, thin=0.22, blush=0, texture=0, rim=None):
    """몸통 비율을 지켜 점 격자 가운데 앉히고 얼굴·볼·결정면을 파낸다.

    자리와 크기는 `lay`(Layout)가 정한다. 같은 프레임을 그리는 `face_art`·`fit_color` 와
    **같은 Layout 을 받아야** 셋이 같은 자리를 잡는다.
    thin 은 얼굴 점을 인정할 면적 비율이라, 낮게 잡아야 한 점 폭이 안 되는 입선이 남는다.
    볼터치는 파내지 않는다(blush=0 이 기본). 색이 붙기 전에는 한 칸 걸러 파서 표시했는데,
    색으로 칠할 수 있게 된 뒤로는 그 구멍이 볼에 낀 검은 점으로 보인다. 색만 입힌다.
    texture 는 삼각면을 파낼 밝기 백분위다. 기본은 끔이다. 삼각형 한 변이 26칸에서 1.6점뿐이라
    파낸 자리가 면으로 안 읽히고 얽은 자국이 된다. rim 은 실루엣을 지킬 테두리 두께(점)로, 비우면
    칸 수에 비례해 잡는다. 칸이 늘면 점이 잘아져 같은 두께로는 테두리가 헐기 때문이다.
    squeeze 는 세로 눌림이다. 터미널 칸이 가로 1 세로 2 보다 길면 점이 세로로 늘어져
    캐릭터가 홀쭉해 보이므로, 그만큼 세로를 미리 줄여 둔다.
    """
    body, face = m["body"], m["face"]
    if rim is None:
        rim = max(2, round(lay.cw / 13))
    W, H, tw, th, ox, oy = lay.W, lay.H, lay.tw, lay.th, lay.ox, lay.oy

    def put(arr, mode, keep=False):
        a = np.asarray(arr, dtype=np.float64)
        lo, hi = (float(a.min()), float(a.max())) if keep else (0.0, 1.0)
        v = (a - lo) / max(1e-9, hi - lo) * 255 if keep else a * 255
        s = Image.fromarray(v.astype(np.uint8)).resize((tw, th), mode)
        c = Image.new("L", (W, H), 0)
        c.paste(s, (ox, oy))
        out = np.asarray(c).astype(np.float64) / 255.0
        return out * (hi - lo) + lo if keep else out

    facemask = put(face, Image.BOX) > thin
    grid = (put(body, Image.LANCZOS) > 0.5) & ~facemask
    blushmask = put(m["blush"], Image.BOX) > blush
    if blush:
        yy, xx = np.mgrid[0:H, 0:W]
        grid &= ~(blushmask & ((xx + yy) % 2 == 0))
    if texture:
        # 눕힌 삼각면을 값 그대로 점 격자에 면적평균으로 옮긴다. 이진 마스크를 줄이면
        # 한 칸에 못 미치는 면이 문턱을 못 넘어 통째로 사라진다.
        hpd = put(m["facet"], Image.BOX, keep=True)
        solid = np.asarray(Image.fromarray((grid * 255).astype(np.uint8))
                           .filter(ImageFilter.MinFilter(2 * rim + 1))) > 127
        near = np.asarray(Image.fromarray(((facemask | blushmask) * 255).astype(np.uint8))
                          .filter(ImageFilter.MaxFilter(5))) > 127
        core = solid & ~near & (put(m["inner"], Image.BOX) > 0.9)
        if core.any():
            grid &= ~(core & (hpd < np.percentile(hpd[core], texture)))
    return braille(["".join("#" if p else "." for p in r) for r in grid])


def scale_for(paths, cw=26, ch=11, pad=1, squeeze=0.909):
    """여러 표정이 같은 크기로 나오도록 가장 빡빡한 배율을 고른다."""
    return min(Layout.fill(masks(p)["body"].shape, cw, ch, pad, squeeze) for p in paths)


def _components(mask, min_px=200):
    """4이웃 연결성분. 얼굴 마스크만 훑으므로 순수 파이썬으로도 충분히 빠르다."""
    seen = np.zeros(mask.shape, bool)
    out = []
    for y, x in np.argwhere(mask):
        if seen[y, x]:
            continue
        q = deque([(y, x)])
        seen[y, x] = True
        px = []
        while q:
            cy, cx = q.popleft()
            px.append((cy, cx))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1] \
                        and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    q.append((ny, nx))
        if len(px) >= min_px:
            out.append(np.array(px))
    return out


def split_face(m):
    """얼굴 마스크를 눈과 입으로 가른다. 가장 아래에 있는 덩어리가 입이다.

    미소는 눈 둘에 입 하나, 윙크는 눈 하나에 윙크 획 하나와 입 하나다. 윙크 획은 눈과
    같은 높이라 눈 쪽으로 묶인다. 그래야 눈 변형이 윙크에도 그대로 걸린다.
    """
    comps = _components(m["face"])
    if not comps:
        return [], None
    mouth = max(comps, key=lambda c: c[:, 0].mean())
    return [c for c in comps if c is not mouth], mouth


def _fill(w, h):
    """뜬 눈. 원화 눈은 꽉 찬 타원이라 네 귀만 덜어 낸다."""
    out = [(y, x) for y in range(h) for x in range(w)]
    if w >= 4 and h >= 3:
        out = [(y, x) for y, x in out
               if not ((y in (0, h - 1)) and (x in (0, w - 1)))]
    return out


def _curve(w, h, kind):
    """입 곡선. 칸마다 줄을 정하고 이웃 칸 사이를 이어 끊기지 않게 한다.

    🔴칸마다 점 하나만 찍으면 가파른 구간이 계단으로 끊겨 실선으로 안 보인다. 원화 입도
    가운데는 한 줄, 양 끝은 두세 줄 두께다(36칸에서 12x4점). 이웃과의 줄 차이를 메우면
    같은 결이 나온다.
    """
    c = (w - 1) / 2 if w > 1 else 1
    def row(x):
        t = ((x - c) / c) ** 2 if c else 0
        r = (h - 1) * (1 - t) if kind in ("smile", "big") else (h - 1) * t
        return min(h - 1, max(0, round(r)))
    if kind == "big":
        return sorted({(y, x) for x in range(w) for y in range(row(x) + 1)})
    return _trace(w, h, row)


def _lower(w, h):
    """반쯤 감은 눈. 아래 절반만 남긴다."""
    k = max(1, h // 2)
    return [(y, x) for y in range(h - k, h) for x in range(w)]


def _ring(w, h):
    """놀란 눈. 자리가 좁으면 속을 못 비우므로 꽉 채운다."""
    if w < 3 or h < 3:
        return _fill(w, h)
    return [(y, x) for y in range(h) for x in range(w)
            if y in (0, h - 1) or x in (0, w - 1)]


def _trace(w, h, rowfn):
    """칸마다 줄을 정하고 이웃 사이를 이어 한 점 두께의 획으로 만든다.

    🔴칸마다 점 하나만 찍으면 가파른 구간에서 줄이 건너뛰어 획이 끊긴다. 사이 줄은 더
    가까운 칸 쪽에 붙여 메운다. 굵게 메우면 획이 덩어리가 된다.
    """
    rows = [min(h - 1, max(0, round(rowfn(x)))) for x in range(w)]
    out = {(r, x) for x, r in enumerate(rows)}
    for x in range(w - 1):
        r0, r1 = rows[x], rows[x + 1]
        step = 1 if r1 >= r0 else -1
        for y in range(r0, r1, step):
            near0, near1 = abs(y - r0), abs(y - r1)
            # 딱 가운데 줄은 획이 좌우로 안 기울도록 진행 방향으로 몰아 준다
            same = x if step > 0 else x + 1
            col = same if near0 == near1 else (x if near0 < near1 else x + 1)
            out.add((y, col))
    return sorted(out)


def _caret(w, h, up=True):
    """웃는 눈 `^` 와 뾰로통한 눈 `v`. 폭이 세 점은 되어야 꺾이는 것이 보인다."""
    if w < 3 or h < 2:
        return None
    c = (w - 1) / 2
    lo, hi = (h - 1, 0) if up else (0, h - 1)
    return _trace(w, h, lambda x: lo + (hi - lo) * (1 - abs(x - c) / c))


def _cross(w, h):
    """뻗은 눈 `x`. 두 대각선을 각각 이어 긋는다."""
    if w < 3 or h < 3:
        return None
    a = _trace(w, h, lambda x: (h - 1) * x / (w - 1))
    b = _trace(w, h, lambda x: (h - 1) * (w - 1 - x) / (w - 1))
    return sorted(set(a) | set(b))


def _arc(w, h, kind):
    """입. 가로 x 마다 포물선으로 줄을 정한다. 끝이 위면 웃음, 아래면 시무룩이다."""
    if w < 2:
        return [(h - 1, x) for x in range(w)]
    return _curve(w, h, kind)


def _blob(w, h):
    """동그란 입. 상자를 꽉 채우는 타원이다. 상자 자체를 좁게 잡아 놓았다."""
    cy, cx = (h - 1) / 2, (w - 1) / 2
    ry, rx = max(0.5, h / 2), max(0.5, w / 2)
    out = [(y, x) for y in range(h) for x in range(w)
           if ((y - cy) / ry) ** 2 + ((x - cx) / rx) ** 2 <= 1.05]
    return out or [(h // 2, w // 2)]


def _zig(w, h):
    """삐죽한 입. 톱니 두 번이 들어가야 삐죽한 것으로 읽힌다."""
    if w < 4 or h < 2:
        return _line(w, h)
    return _trace(w, h, lambda x: (h - 1) * abs((x * 4 / (w - 1)) % 2 - 1))


def _line(w, h):
    """일자 입·감은 눈."""
    return [(h // 2, x) for x in range(w)]


EYE_ART = {
    "뜬눈": lambda w, h: _fill(w, h),
    "반쯤": _lower,
    "감음": lambda w, h: _line(w, 1),
    "크게": lambda w, h: _fill(w, h),
    "기쁨": lambda w, h: _caret(w, h, True),
    "뾰로통": lambda w, h: _caret(w, h, False),
    "놀람": _ring,
    "뻗음": _cross,
    "찡그림": None,                      # 짝마다 달라 `_wedge` 를 좌우로 나눠 쓴다
    "일자": lambda w, h: _line(w, 1),
}
# 눈 상자를 원화 눈 대비 몇 배로 잡을지. 획을 그리는 모양은 상자가 커야 꺾임이 남는다.
EYE_BOX = {"뜬눈": (1.15, 1.2), "반쯤": (1.15, 1.2),
           "크게": (1.45, 1.45), "놀람": (1.45, 1.45), "기쁨": (1.3, 1.5),
           "뾰로통": (1.3, 1.5), "뻗음": (1.3, 1.5), "찡그림": (1.3, 1.5),
           "감음": (1.15, 1.0)}

MOUTH_ART = {
    "원본": lambda w, h: _arc(w, h, "smile"),
    "웃음": lambda w, h: _arc(w, h, "smile"),
    "크게웃음": lambda w, h: _arc(w, h, "big"),
    "시무룩": lambda w, h: _arc(w, h, "frown"),
    "동그람": _blob,
    "일자": lambda w, h: _line(w, 1),
    "삐죽": _zig,
}
MOUTH_BOX = {"크게웃음": (0.9, 1.3), "동그람": (0.5, 1.3), "일자": (0.8, 1.0),
             "삐죽": (0.9, 1.2), "웃음": (1.0, 1.0), "시무룩": (1.0, 1.0)}


def _bar(wd, hd):
    """가로 막대 한 줄. 감은 눈."""
    return [(hd // 2, x) for x in range(wd)]


def _wedge(wd, hd, flip=False):
    """`<` 획. 칸이 좁으면 못 그리므로 None 을 돌려 부르는 쪽이 막대로 물러나게 한다.

    🔴원화 획은 두 점 두께다. 원본2 의 획(115x98px)을 3x3 점으로 줄이면
    `.##/##./.##` 가 나오는데, 한 점 두께로 그으면 `.##/#../.##` 가 되어 너무 뾰족하다.
    위팔과 아래팔을 각각 이어 긋고 가로로 한 점씩 살을 붙인다.
    """
    if wd < 2 or hd < 3:
        return None
    mid = hd // 2
    span = max(1, wd - 1)
    up = _trace(wd, hd, lambda x: mid * (1 - x / span))
    down = _trace(wd, hd, lambda x: mid + (hd - 1 - mid) * x / span)
    out = set(up) | set(down)
    out |= {(y, x + 1) for y, x in list(out) if x + 1 < wd}
    out = sorted(out)
    return [(y, wd - 1 - x) for y, x in out] if flip else out


SHAPES = {"-": _bar, "<": _wedge}


def face_art(m, lay, eye="뜬눈", mouth="원본"):
    """눈과 입을 점 격자에 찍어 새 얼굴 마스크를 만든다.

    자리와 크기는 원화에서 재고(`face0`), 모양은 `EYE_ART`·`MOUTH_ART` 패턴으로 찍는다.
    눈도 입도 점을 파내서 만든다. 🔴입만 안 파내고 그 칸 점 색을 입 색으로 바꿔 봤더니
    몸 색과 밝기 차가 작아 26칸에서는 입이 아예 안 보였다. 파낸 자리는 검게 나오지만
    모양이 점 단위로 남는다.
    🔴원화를 밝기 문턱으로 잘라 줄이는 방식은 두 눈이 점 경계에 서로 다르게 떨어져 좌우가
    다른 모양이 되고(36칸에서 왼눈 두 줄 오른눈 한 줄), 새 모양이 안 덮은 원화 눈이 몸통
    색에 섞여 눈 옆 칸이 올리브색 얼룩이 됐다. 점 칸을 먼저 정하고 그 칸을 원화 좌표로
    되돌려 채우면 줄일 때 그 점만 정확히 찬다.
    """
    h, w, tw, th = lay.h, lay.w, lay.tw, lay.th
    face = np.zeros(m["face"].shape, bool)
    mouth_top = None

    def stamp(cells, r0, c0):
        for ry, rx in cells:
            y0, y1, x0, x1 = lay.to_src(r0, c0, ry, rx)
            if y1 > y0 and x1 > x0:
                face[y0:y1, x0:x1] = True

    base = dict(m)
    base["face"] = m.get("face0", m["face"])
    eyes, lips = split_face(base)
    eyes = sorted(eyes, key=lambda c: c[:, 1].mean())

    if eyes:
        # 두 눈 상자는 평균으로 맞춘다. 원화가 84x94 와 86x103 으로 짝이 안 맞아서, 각자
        # 크기를 쓰면 같은 모양을 찍어도 점 수가 달라진다. 자리는 눈마다 따로 반올림해
        # 원화의 높이 차이(왼눈이 위)는 남긴다.
        bw = np.mean([np.ptp(c[:, 1]) + 1 for c in eyes]) * tw / w
        bh = np.mean([np.ptp(c[:, 0]) + 1 for c in eyes]) * th / h
        for i, c in enumerate(eyes):
            bx, by = EYE_BOX.get(eye, (1.0, 1.0))
            ew = max(1, round(bw * bx))
            eh = max(1, round(bh * by))
            if eye == "찡그림":
                cells = _wedge(ew, eh, i == 0) or _line(ew, 1)
            else:
                cells = EYE_ART[eye](ew, eh) or _line(ew, 1)
            hh = max(r for r, _ in cells) + 1
            cy = (c[:, 0].min() + c[:, 0].max()) / 2
            cx = (c[:, 1].min() + c[:, 1].max()) / 2
            stamp(cells, round(lay.row(cy) - hh / 2), round(lay.col(cx) - ew / 2))

    if lips is not None:
        bx, by = MOUTH_BOX.get(mouth, (1.0, 1.0))
        mw = max(2, round((np.ptp(lips[:, 1]) + 1) * tw / w * bx))
        mh = max(1, round((np.ptp(lips[:, 0]) + 1) * th / h * by))
        cells = MOUTH_ART[mouth](mw, mh)
        hh = max(r for r, _ in cells) + 1
        cy = (lips[:, 0].min() + lips[:, 0].max()) / 2
        cx = (lips[:, 1].min() + lips[:, 1].max()) / 2
        r0 = round(lay.row(cy) - hh / 2)
        stamp(cells, r0, round(lay.col(cx) - mw / 2))
        mouth_top = r0 + min(r for r, _ in cells)

    out = dict(m)
    out["face"] = face
    # 볼 높이를 여기에 맞춘다. 입을 찍은 점 줄을 그대로 넘겨야 프레임마다 간격이 안 흔들린다.
    if mouth_top is not None:
        out["mouth_top"] = mouth_top
    return out


def fit_color(m, lay, sub=5, gain=1.0):
    """`fit` 과 똑같은 자리에서 칸별 색을 낸다. 같은 Layout 을 받으므로 자리가 어긋날 수 없다.

    세 가지를 지킨다.
    1. 🔴몸 밖 픽셀을 빼고 평균한다. 그냥 평균하면 테두리 칸이 투명한 검정과 섞여 어두워지고
       실루엣이 뭉개진다.
    2. 🔴눈·입도 뺀다. 파낸 자리를 색에도 섞으면 눈 둘레 칸이 탁해진다. 파내는 것은 점이 하고
       색은 몸통만 나른다.
    3. 🔴칸 하나가 삼각면보다 크다(칸 약 64px · 삼각면 47px). 칸 전체를 평균하면 면이 서너 개
       섞여 무늬가 사라지므로, 칸을 sub(5) 등분해 가운데 조각만 쓴다. 그러면 칸마다 한 면의 색을
       집어 모자이크가 된다.
    gain 은 부르는 쪽이 나중에 칸 색 대비를 벌릴 배수다. 볼색은 원화 값 그대로 찍어야 하므로
    미리 그만큼 나눠 두면 벌린 뒤에 제 색으로 떨어진다.
    반환 = (ch, cw, 3) 실수 배열과 칸이 몸을 덮는지 나타내는 (ch, cw) 불리언.
    """
    body = m["body"]
    warm = m["blush"]
    # 🔴볼도 몸 색에서 뺀다. 남겨 두면 볼 둘레 칸이 분홍끼를 띠어 도장 밖까지 볼로 보인다.
    keep = body & ~m["face"] & ~m.get("face0", m["face"]) & ~warm
    cw, ch, W, H = lay.cw, lay.ch, lay.W, lay.H
    h, w, tw0, th0 = lay.h, lay.w, lay.tw0, lay.th0
    tw, th, ox, oy = lay.tw, lay.th, lay.ox, lay.oy

    def put(arr, chan):
        """원본을 그 자리에 놓고 칸을 sub 등분한 격자로 줄인다."""
        shape = (tw, th) if chan == 1 else (tw, th)
        im = Image.fromarray(arr.astype(np.uint8)).resize(shape, Image.BOX)
        base = Image.new(im.mode, (W, H), 0)
        base.paste(im, (ox, oy))
        small = base.resize((cw * sub, ch * sub), Image.BOX)
        return np.asarray(small).astype(np.float64)

    num = put(np.clip(m["rgb"], 0, 255) * keep[..., None], 3)
    den = put(keep * 255, 1) / 255.0
    cov = put(body * 255, 1) / 255.0
    mask = put(m["face"] * 255, 1) / 255.0

    mid = sub // 2
    fine = num[mid::sub, mid::sub] / np.maximum(den[mid::sub, mid::sub], 1e-6)[..., None]
    wide = (num.reshape(ch, sub, cw, sub, 3).sum(axis=(1, 3))
            / np.maximum(den.reshape(ch, sub, cw, sub).sum(axis=(1, 3)), 1e-6)[..., None])
    inside = cov.reshape(ch, sub, cw, sub).mean(axis=(1, 3)) > 0.25

    # 가운데 조각이 눈·입뿐이면 그 칸은 색이 없다. 칸 전체로, 그래도 없으면 몸통 평균으로 물린다
    thin = den[mid::sub, mid::sub] < 0.15
    col = np.where(thin[..., None], wide, fine)
    mean = col[inside & ~thin].mean(axis=0) if (inside & ~thin).any() else np.array([200.0] * 3)
    blank = den.reshape(ch, sub, cw, sub).mean(axis=(1, 3)) < 0.05
    col[blank] = mean


    # 🔴볼터치는 몸을 따라 늘어나면 안 된다. 몸이 눌리면 가로로 퍼져 3x1 이 4x1 이 되고
    # 프레임마다 모양이 바뀌어 번지는 것처럼 보인다. 자리만 몸을 따라가고 크기는 고정한다.
    if warm.any():
        # 🔴볼은 원화 색(230,207,174) 그대로여야 한다. 그냥 찍으면 뒤에 걸리는 GAIN 이
        # 몸통 평균에서 세 배 밀어내 (255,133,104) 진한 살구색으로 튄다.
        tone = np.clip(m["rgb"], 0, 255)[warm].mean(axis=0)
        blobs = _components(warm, min_px=200)
        if blobs:
            # 크기는 볼 한 짝의 원본 크기에서 뽑는다. 두 짝을 한꺼번에 재면 뺨 사이 거리까지
            # 폭으로 잡혀 얼굴을 통째로 덮는다. 자세와 무관한 `tw0`·`th0` 로 재서 고정한다.
            one = max(blobs, key=len)
            # 한 칸짜리 볼은 뺨이 아니라 흘린 점으로 보인다. 최소 두 칸은 준다.
            fh = max(1, round(np.ptp(one[:, 0]) * th0 / (4 * h) * 0.8))
            # 🔴세로는 한 칸 아래로 못 내려간다. 참값이 0.33~0.77칸이라 늘 1칸으로 올라가고,
            # 그래서 26칸 이하에서는 2x1칸(화면비 0.91:1)으로 원화(165x110px, 1.5:1)보다
            # 덜 납작하다. 가로를 세로에 맞춰 3칸으로 넓혀 봤더니 볼이 너무 커 보였다.
            # 한 칸이 이미 원화 볼 높이보다 크므로 이 크기에서는 정직한 폭이 낫다.
            fw = max(2, round(np.ptp(one[:, 1]) * tw0 / (2 * w) * 0.8))
            # 🔴얼굴이 한 점이라도 걸친 칸은 물론, 그 옆 칸에도 안 찍는다. 칸 안에서 눈은
            # 파낸 구멍이라 같은 칸에 볼색을 칠하면 구멍이 볼색 테두리를 두른 꼴이 되고,
            # 옆 칸이면 눈과 볼이 맞닿아 붙어 보인다. 문턱을 0.15 로 두었을 때 5~14%
            # 걸친 칸이 통과해 실제로 겹쳤다.
            # 🔴막는 자리는 원화 눈·입과 그려 넣은 눈·입을 **둘 다** 본다. 원화만 보면
            # 눈을 키우는 표정(크게·놀람 1.45배, 기쁨 1.3배)에서 커진 눈에 볼이 겹치고
            # (36칸 승인대기·완료·놀람 등 9프레임), 그린 것만 보면 파내지 않는 입을
            # 놓쳐 볼이 입 위로 올라앉는다.
            keep_face = m.get("face0", m["face"]) | m["face"]
            fmask = put(keep_face * 255, 1) / 255.0
            hit = fmask.reshape(ch, sub, cw, sub).mean(axis=(1, 3)) > 0
            grown = np.zeros((ch + 2, cw + 2), bool)
            grown[1:-1, 1:-1] = hit
            near = np.zeros_like(hit)
            for dyy in (0, 1, 2):                     # 대각선까지 여덟 방향
                for dxx in (0, 1, 2):
                    near |= grown[dyy:dyy + ch, dxx:dxx + cw]
            # 🔴줄은 입의 윗변에 맞춘다. 원화 두 장을 재면 볼 평균중심과 입 윗변이 거의
            # 같은 높이다(원본1 40.2% 대 39.5% · 원본2 42.8% 대 43.0%). 입 무게중심은
            # 45~47% 로 다섯 점이나 낮아서, 거기 맞추면 입이 두 줄에 걸칠 때 볼이 아랫줄로
            # 떨어져 입보다 낮아 보인다. 두 짝이 한 줄을 같이 써야 크기도 같아진다.
            # 🔴그린 입의 점 줄을 그대로 쓴다. 원화 마스크에서 따로 재서 반올림하면 몸이
            # 눌릴 때 입은 한 줄 올라가는데 볼은 안 올라가, 간격이 1과 2 사이를 오간다
            # (36칸 작업중에서 실제로 그랬다).
            # 🔴내림이다. 5.85 는 5번 칸 안에 있는데 반올림하면 6번 칸으로 내려가 볼이
            # 입 아래로 떨어진다. 칸 번호는 그 점을 품은 칸이다.
            if m.get("mouth_top") is not None:
                top = int(m["mouth_top"]) // 4 - (fh - 1) // 2
            else:
                others = [c for c in _components(keep_face) if len(c) > 200]
                if others:
                    mouth = max(others, key=lambda c: c[:, 0].mean())
                    top = int(lay.row(mouth[:, 0].min()) / 4 - (fh - 1) / 2)
                else:
                    top = int(np.mean([lay.row(c[:, 0].mean()) / 4
                                       for c in blobs]) - (fh - 1) / 2)
            mid = np.mean([c[:, 1].mean() for c in blobs])
            for c in blobs:
                cx = lay.col(c[:, 1].mean()) / 2
                y0 = max(0, top)
                x0 = max(0, int(cx - (fw - 1) / 2))
                # 🔴눈에 걸리면 바깥으로 비키고, 그래도 걸리면 걸린 쪽부터 줄인다.
                # 눈은 상태마다 크기가 달라(반쯤·크게·기쁨) 걸치는 폭이 매번 다르다.
                # 늘리지는 않는다. 볼이 커지면 원화와 달라 보인다.
                out = 1 if c[:, 1].mean() > mid else -1
                # 🔴한 칸 띄우는 것을 먼저 시도하고, 자리가 없으면 맞닿는 것까지 허용한다.
                # 좁은 격자에서 띄우기를 고집하면 볼이 몸 가장자리로 쫓겨나 점 하나만 남는다.
                width = fw
                placed = False
                base_y = y0
                # 🔴비킬 자리를 넉넉히 본다. 좌우 네 자리만 보던 때는 눈을 키우는 표정
                # (크게·놀람 1.45배, 기쁨 1.3배)에서 성한 자리를 못 찾아 겹친 채 찍혔다.
                for busy in (near, hit):
                    free = lambda a, n, b: (n > 0 and 0 <= a and a + n <= cw
                                            and 0 <= b and b + fh <= ch
                                            and not busy[b:b + fh, a:a + n].any()
                                            and inside[b:b + fh, a:a + n].all())
                    # 줄은 고정한다. 위아래로도 비키게 두면 입과의 간격이 프레임마다 달라진다
                    for dyy in (0,):
                        for shift in (0, out, 2 * out, 3 * out, -out, -2 * out, 4 * out):
                            if free(x0 + shift, fw, base_y + dyy):
                                x0, y0, placed = x0 + shift, base_y + dyy, True
                                break
                        if placed:
                            break
                    if placed:
                        break
                if not placed:
                    # 그래도 자리가 없으면 걸린 쪽부터 납작하게 줄인다
                    for n in range(fw - 1, 0, -1):
                        for a in (x0 if out > 0 else x0 + (fw - n),
                                  x0 + (fw - n) if out > 0 else x0):
                            if free(a, n, y0):
                                x0, width, placed = a, n, True
                                break
                        if placed:
                            break
                if not placed:
                    continue
                spot = np.zeros(busy.shape, bool)
                spot[y0:y0 + fh, x0:x0 + width] = True
                spot &= ~hit          # 마지막 안전장치. 눈·입 칸에는 어떤 경우에도 안 찍는다
                col[spot] = mean + (tone - mean) / gain
                continue
    return col, inside


def headroom_scale(masks_, poses, cw=26, ch=11, squeeze=0.909, pad=1):
    """가장 크게 늘어나는 프레임이 격자를 안 넘도록 배율을 한 번만 정한다.

    스쿼시는 세로를 늘리고 점프는 위로 올린다. 정지 그림 기준으로 꽉 채워 두면 늘어난
    프레임의 머리가 잘린다. 애니메이션 전체가 한 배율을 써야 상태가 바뀔 때 크기도 안 튄다.
    poses 는 (가로배율, 세로배율, 가로이동, 세로이동) 목록이다.

    🔴늘어난 프레임은 바닥을 붙인 채 위로만 자라므로, 남는 자리는 격자 높이가 아니라
    **위쪽 여백**으로 따져야 한다. `fit` 이 두는 윗변은 (H-th0)/2 + th0 - th - lift 라
    이것이 0 이상이려면 th0 * (sy - 0.5) <= H/2 - lift 여야 한다. 전에는 격자 전체
    높이로 따져서 놀람 2·3번의 머리가 잘렸다(윗줄 폭 31점, 몸통 폭 55점).
    """
    W, H = cw * 2, ch * 4
    base = min(Layout.fill(m["body"].shape, cw, ch, pad, squeeze) for m in masks_)
    tw0 = max(m["body"].shape[1] for m in masks_) * base
    th0 = max(m["body"].shape[0] for m in masks_) * base * squeeze
    sx = max(p[0] for p in poses)
    sy = max(p[1] for p in poses)
    lift = max(max(-p[3], 0) for p in poses)
    sway = max(abs(p[2]) for p in poses)
    room = 1.0
    if sy > 0.5:
        room = (H / 2 - pad - lift) / (th0 * (sy - 0.5))
    return base * min(1.0, (W - 2 * pad - 2 * sway) / (tw0 * sx), room)


if __name__ == "__main__":
    def opt(name, default):
        if name not in sys.argv:
            return default
        i = sys.argv.index(name)
        return float(sys.argv[i + 1]) if len(sys.argv) > i + 1 else default

    p = sys.argv[1]
    cw = int(sys.argv[2]) if len(sys.argv) > 2 else 26
    ch = int(sys.argv[3]) if len(sys.argv) > 3 else 11
    if "--dither" in sys.argv:
        bd = float(sys.argv[4]) if len(sys.argv) > 4 else 0.72
        print(dots(p, cw, ch, bd))
    else:
        m = masks(p)
        lay = Layout(m["body"].shape, cw, ch, squeeze=opt("--squeeze", 0.909))
        print(fit(m, lay, texture=opt("--texture", 0)))
