#!/bin/zsh
# 플밍이를 창 하나에 띄워 계속 돌린다. statusLine 과 달리 12fps 로 자기가 다시 그린다.
# 파인더에서 더블클릭하면 터미널 창이 열린다.
cd "$(dirname "$0")"
printf '\033]0;플밍이\007'
exec /usr/bin/python3 plmi/play.py --live
