#!/bin/bash
# 스프라이트를 다시 굽고 검사를 돌린다. 굽기나 검사가 하나라도 실패하면 멈춘다.
#
#   ./build.sh              네 크기 전부
#   ./build.sh 36 26        고른 크기만. 나머지 크기는 그대로 둔다
#
# numpy 와 pillow 가 필요하다. uv 가 있으면 알아서 끌어온다.
set -e

here=$(cd "$(dirname "$0")" && pwd)
cd "$here"
sizes=""
for c in ${*:-36 26 20 16}; do
    case "$c" in
        ''|*[!0-9]*) echo "칸 수는 숫자로 준다: $c" >&2; exit 1 ;;
    esac
    # 같은 칸 수를 두 번 주면 옮기면서 방금 구운 것을 지운다. 한 번만 굽는다
    case " $sizes " in *" $c "*) continue ;; esac
    sizes="$sizes $c"
done

if command -v uv > /dev/null; then
    # 저장소 바깥 폴더의 파이썬 프로젝트를 따라가지 않게 한다
    py="uv run --no-project --quiet --with numpy --with pillow python"
else
    py="python3"
    python3 -c "import numpy, PIL" 2>/dev/null || {
        echo "numpy 와 pillow 가 필요하다. uv 를 깔거나 pip install numpy pillow" >&2
        exit 1
    }
fi

# 임시 폴더에 다 구운 뒤에 옮긴다. 굽다 멈추면 저장소 스프라이트는 그대로 남는다
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
for c in $sizes; do
    $py plmi/anim.py --cols "$c" --out "$tmp/$c"
done
for c in $sizes; do
    # 파일 이름의 줄 수는 굽고 나서 정해지므로 그 칸 수의 옛 파일을 지우고 넣는다
    rm -f plmi/sprites/anim/플밍이_*_"${c}"x*.json
    mv "$tmp/$c"/*.json plmi/sprites/anim/
done

echo
echo "검사"
python3 tests/run.py
