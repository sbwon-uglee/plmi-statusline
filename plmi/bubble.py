"""플밍이 옆에 말풍선을 붙인다.

한글은 터미널에서 두 칸을 먹는다. 글자 수로 폭을 재면 상자가 어긋나므로
`unicodedata.east_asian_width` 로 실제 칸 수를 센다.

    python3 plmi/bubble.py "파일 읽는 중" 작업중
"""
import sys
import unicodedata

PAD = "\u2800"                              # 브라유 빈칸. 보통 공백보다 폭이 맞다
COLS = 22                                   # 말풍선 안쪽 한 줄의 칸 수


def width(c):
    """글자 하나가 터미널에서 먹는 칸 수. 결합 부호는 앞 글자에 얹혀 칸을 안 먹는다."""
    if unicodedata.combining(c) or unicodedata.category(c) in ("Mn", "Me"):
        return 0
    return 2 if unicodedata.east_asian_width(c) in ("W", "F") else 1


def cells(s):
    """터미널이 실제로 쓰는 칸 수."""
    return sum(width(c) for c in s)


def pieces(word, cols):
    """cols 칸보다 넓은 낱말을 칸 수대로 자른다. 안 자르면 상자가 창 검사의 계산보다 넓어진다."""
    out, part = [], ""
    for c in word:
        if part and cells(part + c) > cols:
            out.append(part)
            part = ""
        part += c
    return out + [part]


def wrap(text, cols):
    out, line = [], ""
    for word in (p for w in text.split() for p in pieces(w, cols)):
        cand = f"{line} {word}".strip()
        if cells(cand) > cols and line:
            out.append(line)
            line = word
        else:
            line = cand
    if line:
        out.append(line)
    return out or [""]


def draw(text, shown=None):
    """말풍선을 그린다. 꼬리는 둘째 줄에 달고, 한 줄뿐이면 그 줄에 단다.

    shown 을 주면 앞에서부터 그 글자 수만 보인다. 상자 크기와 줄 바꿈은 text 전체로
    정하므로 보이는 글자 수가 달라도 상자는 그대로다. 공백은 하나로 접어서 센다.
    """
    text = " ".join(text.split())
    body = wrap(text, COLS)
    tail = min(1, len(body) - 1)
    inner = max(cells(l) for l in body)
    if shown is not None:
        seen, at = [], 0
        for l in body:
            if text.startswith(" ", at):
                at += 1                       # 줄 바꿈 자리의 공백. 긴 낱말을 자른 자리에는 없다
            seen.append(l[:max(0, shown - at)])
            at += len(l)
        body = seen
    top = "╭" + "─" * (inner + 2) + "╮"
    bot = "╰" + "─" * (inner + 2) + "╯"
    rows = [top]
    for i, l in enumerate(body):
        edge = "◀" if i == tail else "│"
        rows.append(f"{edge} {l}{' ' * (inner - cells(l))} │")
    rows.append(bot)
    return rows


def beside(art, bub):
    """왼쪽 그림에 오른쪽 상자를 한 줄 내려 붙인다. 사이는 한 칸 띄운다. 상자가 더 길면 그림
    아래를 빈 줄로 늘린다."""
    art = art.split("\n")
    wide = max(len(l) for l in art)
    pad = [""] + bub
    n = max(len(art), len(pad))
    art += [PAD * wide] * (n - len(art))
    pad += [""] * (n - len(pad))
    return "\n".join(a.ljust(wide, PAD) + PAD + b for a, b in zip(art, pad))


if __name__ == "__main__":
    from statusline import frame          # statusline 이 bubble 을 부르므로 여기서만 부른다

    text = sys.argv[1] if len(sys.argv) > 1 else "다음 할 일 정리 중"
    state = sys.argv[2] if len(sys.argv) > 2 else None
    print(beside(frame(state), draw(text)))
