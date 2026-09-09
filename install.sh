#!/bin/bash
# 플밍이를 Claude Code statusLine 에 붙인다. 인자는 plmi/install.py 로 그대로 넘어간다.
#
#   ./install.sh                 사용자 설정에 붙인다
#   ./install.sh --size 36x15    큰 그림으로
#   ./install.sh --uninstall     뗀다
set -e

here=$(cd "$(dirname "$0")" && pwd)

if ! command -v python3 > /dev/null; then
    echo "python3 가 필요하다. 맥이면 기본으로 들어 있고, 없으면 brew install python" >&2
    exit 1
fi

exec python3 "$here/plmi/install.py" "$@"
