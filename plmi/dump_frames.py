"""전 프레임을 HTML 한 장으로 뽑는다. 눈으로 프레임을 골라 보려고 만든 것이다.

    python terminal_char/dump_frames.py

색은 터미널에 나가는 값을 그대로 span 에 넣는다. 같은 그림이 반복되는 프레임은
「몇 번과 같음」으로 표시해 실제로 몇 장이 도는지 보이게 한다.
"""
import datetime
import glob
import html
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ANIM = os.path.join(HERE, "sprites", "anim")
OUT = os.path.expanduser("~/Downloads/플밍이_프레임")
CHARS = "0123456789abcdefghijklmnopq"
ORDER = ["숨쉬기", "작업중", "생각중", "승인대기", "완료", "오류", "놀람", "뾰로통"]


def paint(frame, tint, palette, cw, back=None):
    out = []
    rows = back.split("\n") if back else []
    for y, (line, row) in enumerate(zip(frame.split("\n"), tint.split("\n"))):
        bar = rows[y] if y < len(rows) else ""
        buf, prev = [], (None, None)
        for i, ch in enumerate(line):
            key = row[i] if i < len(row) and i < cw else "."
            bg = bar[i] if i < len(bar) and i < cw else "."
            if (key, bg) != prev:
                if prev not in ((None, None), (".", ".")):
                    buf.append("</span>")
                if (key, bg) != (".", "."):
                    css = []
                    if key != ".":
                        css.append("color:rgb({},{},{})".format(*palette[CHARS.index(key)]))
                    if bg != ".":
                        css.append("background:rgb({},{},{})".format(*palette[CHARS.index(bg)]))
                    buf.append(f'<span style="{";".join(css)}">')
                prev = (key, bg)
            buf.append(html.escape(ch))
        if prev not in ((None, None), (".", ".")):
            buf.append("</span>")
        out.append("".join(buf))
    return "\n".join(out)


def main():
    os.makedirs(OUT, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    sizes = sorted({os.path.basename(f).rsplit("_", 1)[1][:-5]
                    for f in glob.glob(os.path.join(ANIM, "*.json"))},
                   key=lambda s: -int(s.split("x")[0]))
    secs = []
    for size in sizes:
        blocks = []
        for name in ORDER:
            p = os.path.join(ANIM, f"플밍이_{name}_{size}.json")
            if not os.path.exists(p):
                continue
            a = json.load(open(p, encoding="utf-8"))
            seen, cards = {}, []
            backs = a.get("backs") or [None] * len(a["frames"])
            for i, (f, t) in enumerate(zip(a["frames"], a["tints"])):
                same = seen.setdefault(f, i)
                tag = "" if same == i else f"<em>{same}번과 같음</em>"
                cards.append(f'<figure><pre>'
                             f'{paint(f, t, a["palette"], a["cw"], backs[i])}</pre>'
                             f"<figcaption>{i}{tag}</figcaption></figure>")
            beat = f'{a["hold"]}초/장' if a.get("hold") else f'{a["fps"]}fps'
            blocks.append(f"<section><h3>{name}<span>{len(a['frames'])}장 · {beat} · "
                          f"서로 다른 그림 {len(seen)}</span></h3>"
                          f'<div class="grid">{"".join(cards)}</div></section>')
        secs.append(f'<article><h2>{size}</h2>{"".join(blocks)}</article>')

    # 터미널과 같은 글꼴로 그린다. 글꼴이 다르면 같은 문자라도 점 간격과 칸 비율이 달라
    # 화면에서 본 것과 어긋난다. cmux 기본이 JetBrains Mono 다.
    font = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
            'family=JetBrains+Mono:wght@400&display=swap">')
    # 줄 높이는 글꼴의 칸 높이에 맞춘다. JetBrains Mono 는 자간 600/1000 em 에
    # 줄 1020+300 = 1320/1000 em 이라 1.32 다. 1.0 으로 두면 터미널보다 세로로 눌려 보인다.
    style = """
:root { --bg:#F1F4EC; --panel:#FBFCF8; --ink:#1A271F; --muted:#66766B; --line:#D9E0D3; --accent:#2E9463 }
@media (prefers-color-scheme: dark) { :root:not([data-theme=light]) {
  --bg:#101913; --panel:#17231B; --ink:#E4EDE4; --muted:#8A9C8E; --line:#263528; --accent:#6FD79B } }
* { box-sizing:border-box }
body { margin:0; background:var(--bg); color:var(--ink); font-family:"IBM Plex Sans KR",system-ui,sans-serif }
.wrap { max-width:1500px; margin:0 auto; padding:32px 20px 64px }
h1 { font-size:28px; margin:0 0 4px }
.lede { color:var(--muted); margin:0 0 26px }
article { margin-bottom:40px }
h2 { font-size:20px; margin:0 0 12px; padding-bottom:6px; border-bottom:2px solid var(--accent) }
section { margin:0 0 22px }
h3 { font-size:15px; margin:0 0 8px; display:flex; gap:10px; align-items:baseline }
h3 span { font-weight:400; font-size:12px; color:var(--muted) }
.grid { display:flex; flex-wrap:wrap; gap:10px }
figure { margin:0; background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:8px }
pre { margin:0; font-family:"JetBrains Mono",ui-monospace,Menlo,monospace; font-size:12px;
      line-height:1.32; letter-spacing:0; font-variant-ligatures:none; white-space:pre }
figcaption { margin-top:6px; font-size:11px; color:var(--muted); font-variant-numeric:tabular-nums }
figcaption em { font-style:normal; color:var(--accent); margin-left:6px }
"""
    doc = (f"<title>플밍이 전 프레임</title>\n{font}\n<style>{style}</style>\n"
           f'<div class="wrap">\n<h1>플밍이 전 프레임</h1>\n'
           f'<p class="lede">{stamp} · 크기 {len(sizes)}종 · 상태 {len(ORDER)}종. '
           f"색은 터미널에 나가는 값 그대로다.</p>\n" + "".join(secs) + "\n</div>\n")
    dst = os.path.join(OUT, f"플밍이_전프레임_{stamp}.html")
    with open(dst, "w", encoding="utf-8") as f:
        f.write(doc)
    print(dst)


if __name__ == "__main__":
    main()
