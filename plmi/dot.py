"""플밍이 원화를 브라유 점 격자로 옮긴다. 몸통은 통째로 채우고 눈과 입은 파낸다.

1. 원화는 오른쪽 아래로 그림자가 깔려 몸 가장자리가 어둡다. 가장자리를 rim 만큼 깎은
   안쪽에서만 얼굴을 찾는다.
2. 볼터치는 주황이고 눈과 입은 초록 계열이라 색으로 가른다. 볼은 파내지 않고 색으로 칠한다.
3. 입선이 밝아 고정 문턱으로는 빠진다. 얼굴 문턱은 몸통 밝기 중앙값의 drop 배로 잡는다.
4. 브라유 한 칸은 가로 2점 세로 4점이라 칸 비가 1:2 일 때 점이 정사각이다. 칸이 더 길면
   squeeze 로 세로를 미리 줄인다. 값 = 2 / (칸 세로 대 가로 비). 굽는 값은 anim.SQUEEZE 다.

    python3 plmi/dot.py <원화.png> [칸 수] [줄 수] [--squeeze 값]
"""
import sys

from collections import deque

import numpy as np
from PIL import Image, ImageFilter

from sprite import braille


def masks(path, rim=0.02, drop=0.85, warm=10):
    """몸통, 얼굴, 볼터치 마스크와 원화 색을 뽑아 몸통 bbox 로 자른다. `face0`(원화 눈과 입),
    `eyes`, `lips`, `blobs`(볼 덩어리)도 같이 낸다.

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

    ys, xs = np.nonzero(body)
    box = (slice(ys.min(), ys.max() + 1), slice(xs.min(), xs.max() + 1))
    out = {k2: v[box] for k2, v in {"body": body, "face": face, "blush": blush}.items()}
    out["rgb"] = rgb[box]              # 칸 색을 뽑을 때 쓴다
    # 원화 눈과 입 자리. 새로 찍은 모양이 덜 덮어도 원화 눈이 몸 색에 섞이지 않게 색 계산에서 늘 뺀다
    out["face0"] = out["face"]
    # 원화에서 한 번만 재면 되는 덩어리. 표정과 자세마다 다시 훑으면 굽기가 느려진다
    out["eyes"], out["lips"] = split_face(out["face"])
    out["blobs"] = _components(out["blush"])
    return out


class Layout:
    """원화를 점 격자 어디에 얼마로 앉힐지 한 곳에서 정한다. `fit`, `face_art`, `fit_color` 가
    같은 Layout 을 받아 몸과 얼굴과 색이 같은 자리에 앉는다.

    좌표계가 둘이다. 원화 픽셀 `(h, w)` 와 점 격자 `(H, W)`. `tw0` 와 `th0` 는 자세를 주기
    전 기준 크기, `tw` 와 `th` 는 자세를 준 뒤 크기다. **자리는 기준 크기로 잡고 크기만
    자세로 준다.** 눌린 프레임이 바닥을 붙인 채 위로만 줄어야 떡이 공중에 뜨지 않는다.
    """

    __slots__ = ("h", "w", "cw", "ch", "W", "H", "scale", "tw0", "th0", "tw", "th", "ox", "oy")

    def __init__(self, shape, cw, ch, scale=None, pad=1, squeeze=0.909,
                 sx=1.0, sy=1.0, dx=0, dy=0):
        self.h, self.w = shape
        self.cw, self.ch = cw, ch
        self.W, self.H = cw * 2, ch * 4
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
        """격자 점 하나가 덮는 원화 픽셀 범위 (y0, y1, x0, x1)."""
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


def fit(m, lay, thin=0.22):
    """몸통을 lay 자리에 앉히고 얼굴을 파내 브라유 문자열로 낸다.

    thin 은 얼굴 점으로 인정할 면적 비율이라 낮을수록 한 점 폭이 안 되는 입선도 남는다.
    """
    body, face = m["body"], m["face"]
    W, H, tw, th, ox, oy = lay.W, lay.H, lay.tw, lay.th, lay.ox, lay.oy

    def put(arr, mode):
        v = np.asarray(arr, dtype=np.float64) * 255
        s = Image.fromarray(v.astype(np.uint8)).resize((tw, th), mode)
        c = Image.new("L", (W, H), 0)
        c.paste(s, (ox, oy))
        return np.asarray(c).astype(np.float64) / 255.0

    facemask = put(face, Image.BOX) > thin
    grid = (put(body, Image.LANCZOS) > 0.5) & ~facemask
    return braille(["".join("#" if p else "." for p in r) for r in grid])


def _components(mask, min_px=200):
    """4이웃 연결성분. min_px 보다 작은 덩어리는 버린다."""
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


def split_face(face):
    """얼굴 마스크를 눈과 입으로 가른다. 가장 아래에 있는 덩어리가 입이다."""
    comps = _components(face)
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


def _arc(w, h, kind):
    """입 곡선. smile 은 끝이 위, frown 은 아래, big 은 윗변과 곡선 사이를 채운다. w 는 2 이상이다."""
    c = (w - 1) / 2
    def row(x):
        t = ((x - c) / c) ** 2
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
    """가로 점마다 줄을 정하고 이웃 사이를 이어 한 점 두께의 획으로 만든다.

    사이 줄은 더 가까운 쪽 점에 붙인다.
    """
    rows = [min(h - 1, max(0, round(rowfn(x)))) for x in range(w)]
    out = {(r, x) for x, r in enumerate(rows)}
    for x in range(w - 1):
        r0, r1 = rows[x], rows[x + 1]
        step = 1 if r1 >= r0 else -1
        for y in range(r0, r1, step):
            near0, near1 = abs(y - r0), abs(y - r1)
            # 딱 가운데 줄은 줄 번호가 작은 쪽 점에 붙인다. 내려가는 획과 올라가는 획이 좌우 대칭이 된다
            same = x if step > 0 else x + 1
            col = same if near0 == near1 else (x if near0 < near1 else x + 1)
            out.add((y, col))
    return sorted(out)


def _caret(w, h):
    """웃는 눈 `^`. 폭이 세 점은 되어야 꺾이는 것이 보인다."""
    if w < 3 or h < 2:
        return None
    c = (w - 1) / 2
    return _trace(w, h, lambda x: (h - 1) - (h - 1) * (1 - abs(x - c) / c))


def _blob(w, h):
    """동그란 입. 상자를 꽉 채우는 타원이다. 상자는 `MOUTH_BOX` 에서 좁게 잡는다."""
    cy, cx = (h - 1) / 2, (w - 1) / 2
    ry, rx = max(0.5, h / 2), max(0.5, w / 2)
    return [(y, x) for y in range(h) for x in range(w)
           if ((y - cy) / ry) ** 2 + ((x - cx) / rx) ** 2 <= 1.05]


def _zig(w, h):
    """삐죽한 입. 톱니 두 번이 들어가야 삐죽한 것으로 읽힌다."""
    if w < 4 or h < 2:
        return _line(w, h)
    return _trace(w, h, lambda x: (h - 1) * abs((x * 4 / (w - 1)) % 2 - 1))


def _line(w, h):
    """일자 입·감은 눈."""
    return [(h // 2, x) for x in range(w)]


EYE_ART = {
    "뜬눈": _fill,
    "반쯤": _lower,
    "감음": lambda w, h: _line(w, 1),
    "크게": _fill,
    "기쁨": _caret,
    "놀람": _ring,
    "찡그림": None,                      # 짝마다 달라 `_wedge` 를 좌우로 나눠 쓴다
}
# 눈 상자를 원화 눈 대비 몇 배로 잡을지. 획을 그리는 모양은 상자가 커야 꺾임이 남는다.
EYE_BOX = {"뜬눈": (1.15, 1.2), "반쯤": (1.15, 1.2),
           "크게": (1.45, 1.45), "놀람": (1.45, 1.45), "기쁨": (1.3, 1.5),
           "찡그림": (1.3, 1.5), "감음": (1.15, 1.0)}

MOUTH_ART = {
    "미소": lambda w, h: _arc(w, h, "smile"),
    "크게웃음": lambda w, h: _arc(w, h, "big"),
    "시무룩": lambda w, h: _arc(w, h, "frown"),
    "동그람": _blob,
    "일자": lambda w, h: _line(w, 1),
    "삐죽": _zig,
}
MOUTH_BOX = {"미소": (1.0, 1.0), "크게웃음": (0.9, 1.3), "시무룩": (1.0, 1.0),
             "동그람": (0.5, 1.3), "일자": (0.8, 1.0), "삐죽": (0.9, 1.2)}


def _wedge(wd, hd, flip=False):
    """`<` 획. flip 이면 `>` 다. 한 점 두께면 너무 뾰족해 가로로 한 점씩 살을 붙인다.
    칸이 좁으면 None 을 돌려 부르는 쪽이 일자로 물러난다.
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


def face_art(m, lay, eye="뜬눈", mouth="미소"):
    """눈과 입을 점 격자에 찍어 새 얼굴 마스크를 만든다.

    자리와 크기는 원화 눈과 입 덩어리(`m["eyes"]`, `m["lips"]`)에서 재고, 모양은 `EYE_ART` 와
    `MOUTH_ART` 로 찍는다. 눈과 입은 파내므로 검게 나오지만 모양이 점 단위로 남는다. 점 칸을
    먼저 정하고 그 칸을 원화 좌표로 되돌려 채우므로 줄였을 때 그 점만 찬다.
    돌려주는 것은 m 의 사본이다. `face` 를 새 마스크로 바꾸고, 입을 찍었으면 맨 윗점 줄을
    `mouth_top` 에 둔다.
    """
    h, w, tw, th = lay.h, lay.w, lay.tw, lay.th
    face = np.zeros(m["face"].shape, bool)
    mouth_top = None

    def stamp(cells, r0, c0):
        for ry, rx in cells:
            y0, y1, x0, x1 = lay.to_src(r0, c0, ry, rx)
            if y1 > y0 and x1 > x0:
                face[y0:y1, x0:x1] = True

    eyes = sorted(m["eyes"], key=lambda c: c[:, 1].mean())
    lips = m["lips"]

    if eyes:
        # 두 눈은 원화 크기가 조금 달라 상자 크기는 평균으로 맞추고, 자리는 눈마다 따로 잡아
        # 높이 차이는 남긴다
        bw = np.mean([np.ptp(c[:, 1]) + 1 for c in eyes]) * tw / w
        bh = np.mean([np.ptp(c[:, 0]) + 1 for c in eyes]) * th / h
        for i, c in enumerate(eyes):
            bx, by = EYE_BOX[eye]
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
        bx, by = MOUTH_BOX[mouth]
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
    """lay 자리에서 칸별 색을 낸다.

    몸 밖, 눈과 입, 볼 픽셀은 빼고 평균한다. 칸이 삼각면보다 커서 칸 전체를 평균하면 무늬가
    사라지므로, 칸을 sub 등분해 가운데 조각의 색을 쓴다. 볼색은 몸 평균에서 떨어진 거리를
    gain 으로 나눠 찍는다. 부르는 쪽이 나중에 대비를 벌리므로 미리 줄여 둔다.
    반환 = (ch, cw, 3) 실수 배열과 칸이 몸을 덮는지 나타내는 (ch, cw) 불리언.
    """
    body = m["body"]
    blush = m["blush"]
    # 볼도 몸 색에서 뺀다. 남기면 볼 둘레 칸이 분홍빛을 띤다
    keep = body & ~m["face"] & ~m["face0"] & ~blush
    cw, ch, W, H = lay.cw, lay.ch, lay.W, lay.H
    h, w, tw0, th0 = lay.h, lay.w, lay.tw0, lay.th0
    tw, th, ox, oy = lay.tw, lay.th, lay.ox, lay.oy

    def put(arr):
        """원화를 그 자리에 놓고 칸을 sub 등분한 격자로 줄인다."""
        im = Image.fromarray(arr.astype(np.uint8)).resize((tw, th), Image.BOX)
        base = Image.new(im.mode, (W, H), 0)
        base.paste(im, (ox, oy))
        small = base.resize((cw * sub, ch * sub), Image.BOX)
        return np.asarray(small).astype(np.float64)

    num = put(np.clip(m["rgb"], 0, 255) * keep[..., None])
    den = put(keep * 255) / 255.0
    cov = put(body * 255) / 255.0

    mid = sub // 2
    fine = num[mid::sub, mid::sub] / np.maximum(den[mid::sub, mid::sub], 1e-6)[..., None]
    wide = (num.reshape(ch, sub, cw, sub, 3).sum(axis=(1, 3))
            / np.maximum(den.reshape(ch, sub, cw, sub).sum(axis=(1, 3)), 1e-6)[..., None])
    inside = cov.reshape(ch, sub, cw, sub).mean(axis=(1, 3)) > 0.25

    # 가운데 조각에 쓸 픽셀이 거의 없으면 칸 전체 평균을, 칸 전체에도 없으면 몸 칸들의 평균 색을 쓴다
    sparse = den[mid::sub, mid::sub] < 0.15
    col = np.where(sparse[..., None], wide, fine)
    mean = col[inside & ~sparse].mean(axis=0) if (inside & ~sparse).any() else np.array([200.0] * 3)
    blank = den.reshape(ch, sub, cw, sub).mean(axis=(1, 3)) < 0.05
    col[blank] = mean

    # 볼 크기는 자세와 무관하게 고정하고 자리만 몸을 따라간다
    if blush.any():
        # 볼 원화 색의 평균. 찍을 때 gain 으로 나눠 부르는 쪽이 벌린 뒤의 색을 맞춘다
        tone = np.clip(m["rgb"], 0, 255)[blush].mean(axis=0)
        blobs = m["blobs"]
        if blobs:
            # 크기는 가장 큰 볼 한 짝을 자세와 무관한 `tw0`, `th0` 로 잰다
            one = max(blobs, key=len)
            fh = max(1, round(np.ptp(one[:, 0]) * th0 / (4 * h) * 0.8))
            # 폭은 원화 비율대로 두되 최소 두 칸이다. 자리가 없을 때만 더 좁아진다
            fw = max(2, round(np.ptp(one[:, 1]) * tw0 / (2 * w) * 0.8))
            # hit 은 원화 눈과 입, 그려 넣은 눈과 입이 한 점이라도 걸친 칸이고 near 는 그 여덟 이웃까지다
            keep_face = m["face0"] | m["face"]
            fmask = put(keep_face * 255) / 255.0
            hit = fmask.reshape(ch, sub, cw, sub).mean(axis=(1, 3)) > 0
            grown = np.zeros((ch + 2, cw + 2), bool)
            grown[1:-1, 1:-1] = hit
            near = np.zeros_like(hit)
            for dyy in (0, 1, 2):
                for dxx in (0, 1, 2):
                    near |= grown[dyy:dyy + ch, dxx:dxx + cw]
            # 볼 줄은 그린 입의 맨 윗점이 든 칸이다(내림). 두 짝이 한 줄을 같이 쓴다
            if "mouth_top" in m:
                top = int(m["mouth_top"]) // 4 - (fh - 1) // 2
            else:
                top = int(np.mean([lay.row(c[:, 0].mean()) / 4
                                   for c in blobs]) - (fh - 1) / 2)
            y0 = max(0, top)
            middle = np.mean([c[:, 1].mean() for c in blobs])   # 두 볼 사이, 원화 가로 좌표

            def free(x, n, busy):
                """x 칸부터 n 칸 폭의 볼 자리가 격자 안이고, busy 에 안 걸리고, 몸 안인지."""
                return (0 <= x and x + n <= cw and y0 + fh <= ch
                        and not busy[y0:y0 + fh, x:x + n].any()
                        and inside[y0:y0 + fh, x:x + n].all())

            for c in blobs:
                x0 = max(0, int(lay.col(c[:, 1].mean()) / 2 - (fw - 1) / 2))
                # 눈이나 입에 걸리거나 몸 밖으로 나가면 옆으로 비킨다. 바깥쪽을 먼저 본다.
                # near 에서 먼저 찾고 없으면 맞닿는 것까지 허용해 hit 에서 찾는다
                side = 1 if c[:, 1].mean() > middle else -1
                width = 0
                for busy in (near, hit):
                    for shift in (0, side, 2 * side, 3 * side, -side, -2 * side, 4 * side):
                        if free(x0 + shift, fw, busy):
                            x0, width = x0 + shift, fw
                            break
                    if width:
                        break
                if not width:
                    # 그래도 자리가 없으면 폭을 줄인다. 같은 폭이면 바깥 끝을 먼저 자른다
                    for n in range(fw - 1, 0, -1):
                        for a in (x0 if side > 0 else x0 + (fw - n),
                                  x0 + (fw - n) if side > 0 else x0):
                            if free(a, n, hit):
                                x0, width = a, n
                                break
                        if width:
                            break
                if width:
                    col[y0:y0 + fh, x0:x0 + width] = mean + (tone - mean) / gain
    return col, inside


def headroom_scale(masks_, poses, cw, ch, squeeze, pad=1):
    """가장 크게 늘어나는 프레임이 격자를 안 넘도록 배율을 한 번만 정한다.

    늘이는 프레임은 세로가 커지고 점프는 위로 올라간다. 자세를 안 준 그림 기준으로 꽉 채우면
    늘어난 프레임의 머리가 잘린다. 애니메이션 전체가 한 배율을 써야 상태가 바뀔 때 크기도 안 튄다.
    poses 는 (가로배율, 세로배율, 가로이동, 세로이동) 목록이다.

    늘어난 프레임은 바닥을 붙인 채 위로만 자라므로 남는 자리는 위쪽 여백으로 따진다.
    `Layout` 이 두는 윗변은 (H-th0)/2 + th0 - th - lift 라 pad 를 남기려면
    th0 * (sy - 0.5) <= H/2 - pad - lift 여야 한다.
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
    args = sys.argv[1:]
    squeeze = 0.909
    if "--squeeze" in args:
        i = args.index("--squeeze")
        squeeze = float(args[i + 1])
        del args[i:i + 2]
    cw = int(args[1]) if len(args) > 1 else 26
    ch = int(args[2]) if len(args) > 2 else 11
    m = masks(args[0])
    print(fit(m, Layout(m["body"].shape, cw, ch, squeeze=squeeze)))
