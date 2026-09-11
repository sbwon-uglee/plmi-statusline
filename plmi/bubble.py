"""플밍이 옆에 말풍선을 붙인다.

한글은 터미널에서 두 칸을 먹는다. 글자 수로 폭을 재면 상자가 어긋나므로
`unicodedata.east_asian_width` 로 실제 칸 수를 센다.

    python terminal_char/bubble.py "파일 읽는 중" 작업중
"""
import os
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PAD = "⠀"                                   # 브라유 빈칸. 보통 공백보다 폭이 맞다


def cells(s):
    """터미널이 실제로 쓰는 칸 수."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def wrap(text, cols):
    out, line = [], ""
    for word in text.split():
        cand = f"{line} {word}".strip()
        if cells(cand) > cols and line:
            out.append(line)
            line = word
        else:
            line = cand
    if line:
        out.append(line)
    return out or [""]


def draw(text, cols=20, tail=1, shown=None):
    """말풍선을 그린다. tail 은 꼬리를 낼 줄 번호(0부터)다.

    shown 을 주면 앞에서부터 그 글자 수만 보이고 나머지 자리는 비워 둔다. 상자 크기와
    줄 바꿈은 text 전체로 먼저 정한다. 보이는 글자로 정하면 한 글자씩 나올 때마다 상자가
    커지고, 줄 바꿈 자리를 넘는 순간 줄 수까지 바뀌어 그림이 밀린다.
    """
    body = wrap(text, cols)
    tail = min(tail, len(body) - 1)          # 한 줄짜리 문구면 꼬리가 사라진다
    inner = max(cells(l) for l in body)
    if shown is not None:
        left, seen = shown, []
        for l in body:
            seen.append(l[:max(0, left)])
            left -= len(l) + 1                # 줄 사이 공백 한 칸도 센다
        body = seen
    top = "╭" + "─" * (inner + 2) + "╮"
    bot = "╰" + "─" * (inner + 2) + "╯"
    rows = [top]
    for i, l in enumerate(body):
        edge = "◀" if i == tail else "│"
        rows.append(f"{edge} {l}{' ' * (inner - cells(l))} │")
    rows.append(bot)
    return rows


def beside(art, bub, gap=1, top=1):
    """왼쪽 그림에 오른쪽 상자를 붙인다. 줄 수가 다르면 짧은 쪽을 빈 줄로 채운다."""
    art = art.split("\n") if isinstance(art, str) else list(art)
    wide = max(len(l) for l in art)
    pad = [""] * top + bub
    n = max(len(art), len(pad))
    art += [PAD * wide] * (n - len(art))
    pad += [""] * (n - len(pad))
    return "\n".join(a.ljust(wide, PAD) + PAD * gap + b for a, b in zip(art, pad))


if __name__ == "__main__":
    from statusline import frame          # statusline 이 bubble 을 부르므로 여기서만 부른다

    text = sys.argv[1] if len(sys.argv) > 1 else "다음 할 일 정리 중"
    state = sys.argv[2] if len(sys.argv) > 2 else None
    print(beside(frame(state), draw(text)))
