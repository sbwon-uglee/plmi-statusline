#!/bin/bash
# 스프라이트를 네 크기로 다시 굽고 검사까지 돌린다. 검사가 하나라도 깨지면 멈춘다.
#
#   ./build.sh              네 크기 전부
#   ./build.sh 36 26        고른 크기만
#
# numpy 와 pillow 가 필요하다. uv 가 있으면 알아서 끌어온다.
set -e

here=$(cd "$(dirname "$0")" && pwd)
cd "$here"
sizes=${@:-"36 26 20 16"}

if command -v uv > /dev/null; then
    py="uv run --quiet --with numpy --with pillow python"
else
    py="python3"
    python3 -c "import numpy, PIL" 2>/dev/null || {
        echo "numpy 와 pillow 가 필요하다. uv 를 깔거나 pip install numpy pillow" >&2
        exit 1
    }
fi

# 줄 수는 빈 줄을 잘라낸 뒤 정해지므로 같은 인자로도 결과 이름이 달라진다.
# 옛 이름의 파일이 남으면 그것을 보고 안 바뀌었다고 오판하게 된다.
echo "옛 스프라이트를 지운다"
rm -f plmi/sprites/anim/*.json

for c in $sizes; do
    $py plmi/anim.py --cols "$c" | head -1
done

echo
echo "검사"
python3 tests/run.py | tail -5
