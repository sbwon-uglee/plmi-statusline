"""전 프레임을 HTML 한 장으로 뽑아 눈으로 확인한다.

    python3 plmi/dump_frames.py [출력 폴더]   HTML 을 둘 곳. 기본은 지금 폴더

색은 터미널에 나가는 값을 그대로 span 에 넣는다. 같은 그림이 반복되는 프레임은
「몇 번과 같음」으로 표시해 실제로 몇 장이 도는지 보이게 한다.
"""
import datetime
import glob
import html
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ANIM = os.path.join(HERE, "sprites", "anim")
CHARS = "0123456789abcdefghijklmn"
ORDER = ["숨쉬기", "작업중", "생각중", "승인대기", "완료", "오류", "놀람", "뾰로통"]


def paint(frame, tint, palette):
    out = []
    for line, row in zip(frame.split("\n"), tint.split("\n")):
        buf, prev = [], None
        for i, ch in enumerate(line):
            key = row[i] if i < len(row) else "."
            if key != prev:
                if prev not in (None, "."):
                    buf.append("</span>")
                if key != ".":
                    buf.append('<span style="color:rgb({},{},{})">'.format(*palette[CHARS.index(key)]))
                prev = key
            buf.append(html.escape(ch))
        if prev not in (None, "."):
            buf.append("</span>")
        out.append("".join(buf))
    return "\n".join(out)


def main():
    out_dir = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.getcwd()
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    sizes = sorted({os.path.basename(f).rsplit("_", 1)[1][:-5]
                    for f in glob.glob(os.path.join(glob.escape(ANIM), "*.json"))},
                   key=lambda s: -int(s.split("x")[0]))
    secs, found = [], set()
    for size in sizes:
        blocks = []
        for name in ORDER:
            p = os.path.join(ANIM, f"플밍이_{name}_{size}.json")
            if not os.path.exists(p):
                continue
            with open(p, encoding="utf-8") as f:
                a = json.load(f)
            found.add(name)
            seen, cards = {}, []
            for i, (frame, t) in enumerate(zip(a["frames"], a["tints"])):
                same = seen.setdefault(frame, i)
                tag = "" if same == i else f"<em>{same}번과 같음</em>"
                cards.append(f'<figure><pre>'
                             f'{paint(frame, t, a["palette"])}</pre>'
                             f"<figcaption>{i}{tag}</figcaption></figure>")
            beat = f'{a["hold"]}초/장' if a.get("hold") else f'{a["fps"]}fps'
            blocks.append(f"<section><h3>{name}<span>{len(a['frames'])}장 · {beat} · "
                          f"서로 다른 그림 {len(seen)}</span></h3>"
                          f'<div class="grid">{"".join(cards)}</div></section>')
        secs.append(f'<article><h2>{size}</h2>{"".join(blocks)}</article>')

    # 터미널과 같은 글꼴(JetBrains Mono)로 그려야 점 간격과 칸 비율이 화면과 맞는다
    font = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
            '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
            'family=JetBrains+Mono:wght@400&display=swap">')
    # 줄 높이는 JetBrains Mono 의 1320/1000 em 에 맞춰 1.32 로 둔다
    style = """
:root { --bg:#F1F4EC; --panel:#FBFCF8; --ink:#1A271F; --muted:#66766B; --line:#D9E0D3; --accent:#2E9463 }
@media (prefers-color-scheme: dark) { :root {
  --bg:#101913; --panel:#17231B; --ink:#E4EDE4; --muted:#8A9C8E; --line:#263528; --accent:#6FD79B } }
* { box-sizing:border-box }
body { margin:0; background:var(--bg); color:var(--ink); font-family:system-ui,sans-serif }
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
    doc = (f'<!doctype html>\n<meta charset="utf-8">\n<title>플밍이 전 프레임</title>\n'
           f"{font}\n<style>{style}</style>\n"
           f'<div class="wrap">\n<h1>플밍이 전 프레임</h1>\n'
           f'<p class="lede">{stamp} · 크기 {len(sizes)}종 · 상태 {len(found)}종</p>\n'
           + "".join(secs) + "\n</div>\n")
    dst = os.path.join(out_dir, f"플밍이_전프레임_{stamp}.html")
    with open(dst, "w", encoding="utf-8") as f:
        f.write(doc)
    print(dst)


if __name__ == "__main__":
    main()
