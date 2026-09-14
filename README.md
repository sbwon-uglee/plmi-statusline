# plmi-statusline

Claude Code 의 statusLine 자리에 사는 플밍이. 어글리랩 마스코트를 브라유 점으로 그려서,
지금 Claude 가 무엇을 하고 있는지에 따라 표정과 자세가 바뀐다.

상태줄 자리에 여러 줄을 쓴다. 기본 크기 26x11 은 11줄이다.

## 설치

```bash
brew trust sbwon-uglee/tap
brew install sbwon-uglee/tap/plmi
plmi
```

Claude Code 를 다시 띄우면 나온다. 필요한 것은 brew 와 python3 뿐이고, python3 는 맥에
기본으로 들어 있다. Homebrew 7 은 Homebrew 가 관리하지 않는 탭을 `brew trust` 로 신뢰해야 읽으므로
처음에 한 번 해 둔다.

올릴 때는 `brew upgrade plmi`. 설정에 적히는 경로에는 버전이 안 들어가서 판을 올려도 그대로다.
뗄 때는 `plmi --uninstall` 뒤에 `brew uninstall plmi`. 순서를 바꾸면 상태줄은 조용히 비고
설정에 안 쓰는 경로가 남는다.

### brew 없이

```bash
git clone https://github.com/sbwon-uglee/plmi-statusline.git ~/.claude/plmi
python3 ~/.claude/plmi/plmi/install.py
```

받는 위치는 아무 데나 된다. 옮기면 `install.py` 를 다시 돌린다. 이렇게 받았다면 아래의
`plmi` 를 `python3 <받은 곳>/plmi/install.py` 로 바꿔 쓴다.

### 옵션

```bash
plmi --size 36x16             크게
plmi --scope project          지금 폴더의 .claude 에만
plmi --scope project --dir ~/work/foo   그 워크스페이스에
plmi --where                  지금 어디에 붙어 있나
plmi --preview                붙이지 않고 4초 돌려 본다
plmi --preview 10 --state 놀람  그 표정으로 10초
plmi --uninstall              뗀다
plmi --dry-run                쓸 내용만 본다
plmi --version                깔린 판
```

크기는 36x16, 26x11, 20x10, 16x8 네 가지를 구워 둔다. 앞이 칸 수, 뒤가 줄 수다.
말풍선까지 합쳐 창보다 큰 크기는 붙일 때 막는다. 그래도 붙이려면 `--force`.

### 다른 크기로 굽기

```bash
plmi --bake 30       30칸으로 굽는다
plmi --size 30x13    구운 것으로 갈아 낀다
```

줄 수는 굽고 나서 정해지므로 칸 수만 준다. 13칸 이상이어야 한다. 결과는 `~/.claude/plmi-sizes` 에 들어가고
판을 올려도 살아남는다. 굽는 데는 numpy 와 pillow 가 필요하다. `uv` 가 있으면 그때만
받아 쓰고, 없으면 이미 깔린 것을 쓴다.

### 환경변수

| 이름 | 기본 | 하는 일 |
|---|---|---|
| `PLMI_SIZE` | 26칸에 가장 가까운 것 | 쓸 크기 |
| `PLMI_BUBBLE` | `1` | 말풍선. `0` 이면 그림만 |
| `PLMI_COLOR` | `1` | 색. `0` 이면 흑백 |

설치기가 `PLMI_SIZE` 를 설정에 넣어 준다. 나머지는 settings.json 의 statusLine 명령 맨 앞에 붙인다.

### 상태

| 상태 | 언제 | 말풍선 |
|---|---|---|
| 숨쉬기 | 아무 일 없을 때 | |
| 작업중 | 도구를 쓰는 중 | 하는 일 한 줄 |
| 생각중 | 사람 말이나 도구 결과를 받고 다음 할 일을 정하는 중 | 무슨 일인지 보는 중, 다음 거 보는 중, 생각하는 중 |
| 승인대기 | 허락을 묻는 도구 호출 뒤 4초 넘게 결과가 안 올 때. auto 와 bypassPermissions 모드, 읽기만 하는 도구는 빼고 | 하는 일 한 줄 |
| 완료 | 답을 마친 뒤 4초 동안 | 끝 |
| 오류 | 도구가 실패했거나 API 오류로 답이 끊겼을 때 | 안 됐어 |
| 놀람 | 하던 일을 사람이 끊었을 때 | 앗 |
| 뾰로통 | 15분 넘게 아무 일이 없을 때 | 심심해 |

말풍선은 일이 난 순간 문구가 한꺼번에 뜨고 뒤에서 점이 하나씩 는다. 심심해와 안 됐어는
점이 세 개까지 차면 3초 쉬었다가 다시 뜨고, 앗과 끝은 한 번만 뜬다. 일하는 중 문구는
사라지지 않고 점만 계속 돈다. 문구는 22자에서 자른다.

설치기는 settings.json 의 `statusLine` 만 고치고 나머지 설정은 그대로 둔다.
쓰기 전에 백업을 뜨고, 플밍이가 아닌 statusLine 이 이미 있으면 `--force` 없이는 덮지 않는다.
그렇게 덮은 원래 설정의 백업은 뗄 때도 지우지 않는다.

## 창으로 띄우기

statusLine 말고 창 하나를 통째로 쓰고 싶으면 저장소를 받은 폴더에서 `플밍이창.command` 를
더블클릭한다. brew 설치에는 이 파일이 들어 있지 않다. 어느 워크스페이스든 가장 최근 대화를
따라가고, statusLine 과 달리 12fps 로 스스로 다시 그린다.

## 상태 반영

Claude Code 가 statusLine 명령에 stdin 으로 넘겨 주는 세션 JSON 의 `transcript_path` 를 읽어
지금 무슨 일이 벌어지는지 알아낸다. 끝 32KB 부터 읽고, 도구 결과 한 줄이 그보다 커서 판정할
것이 모자라면 8MB 까지 넓혀 가며 다시 읽는다. 말풍선 박자도 이 기록에 적힌 사건 시각에 맞춘다.
슬래시 명령 기록, 시스템이 넣은 메타 항목, 압축 요약은 상태를 바꾸지 않는다. 같이 부른 도구 중
결과가 안 온 것이 있으면 그 도구를 보인다.
화면에만 찍혀서 대화에는 아무것도 남기지 않는다.

## 구조

```
plmi/
  statusline.py     statusLine 진입점. 표준 라이브러리만 쓴다
  bubble.py         말풍선
  summary.py        도구 호출을 한 줄 한국어로
  state.py          수동 상태 덮어쓰기
  play.py           창 하나로 계속 돌리는 재생기
  install.py        settings.json 에 붙이고 뗀다
  anim.py           스프라이트를 굽는다. numpy 와 pillow 가 필요하다
  dot.py            점 그림 엔진
  sprite.py         브라유 인코딩
  dump_frames.py    전 프레임을 HTML 로
  sprites/anim/     구워 둔 스프라이트 JSON. 8상태 x 4크기
assets/             원화 PNG. 굽는 데만 쓴다
플밍이창.command     창 하나로 띄우는 실행기. 더블클릭
build.sh            다시 굽고 검사까지
tests/              검사와 돌연변이
```

## 고쳐 쓰기

```bash
./build.sh              네 크기 전부 다시 굽고 검사까지
./build.sh 36 26        고른 크기만
```

인자는 칸 수이고 줄 수는 굽고 나서 정해진다. 굽기나 검사가 실패하면 멈추고, 굽다 멈추면
저장소 스프라이트는 그대로다.
표정 모양은 `plmi/dot.py` 의 `EYE_ART` 와 `MOUTH_ART`, 상태마다 쓸 표정은 `plmi/anim.py` 의
`anims` 에서 고른다.

굽고 나서 눈으로 확인하려면 전 프레임을 HTML 로 뽑는다.

```bash
python3 plmi/dump_frames.py [폴더]
```

`anim.py` 를 직접 부를 때는 그 칸 수의 옛 스프라이트를 먼저 지운다. 파일 이름의 줄 수가
굽고 나서 정해진다.

## 검사

```bash
python3 tests/run.py --quick    몇 초 넘게 걸리는 검사를 빼고
python3 tests/run.py            전부
python3 tests/run.py sprites    이름에 sprites 가 들어간 모듈만
python3 tests/run.py --deep     무작위 입력을 스무 배로
python3 tests/mutate.py         검사가 실제로 잡는지 본다
```

검사는 이 컴퓨터의 홈과 PLMI_ 변수를 못 보게 막고 돈다. 건너뛴 검사는 까닭과 함께 따로 센다.

- 분기마다 적어 둔 사례: 도구 문구, 설치기, 상태 판정, 스프라이트 규칙, 격자 기하
- 무작위로 만든 대화 기록, 문구, 크기에서 늘 지켜야 하는 성질
- 설치기의 시작 설정과 명령을 빠짐없이 이어 붙여 사용자 설정을 잃지 않는지
- brew 모양으로 깔고 올리고 떼는 길, 클론을 옮기고 다시 붙이는 길. 지금 파이썬과 맥 기본 파이썬 둘로
- 실행할 수 있는 파일마다 한 번씩 실제로 돌리기
- README 와 사용법에 적은 플래그, 숫자, 상태, 크기가 코드와 같은지
- 가장 작은 크기를 새로 구워 저장소 스프라이트와 바이트 대조

## 요구 사항

| | |
|---|---|
| 실행 | python3 (3.9 에서 확인). 외부 패키지 없음 |
| 굽기 | numpy, pillow |
| 글꼴 | 브라유 점자(U+2800 부터)를 그리는 고정폭 글꼴. JetBrains Mono 기준으로 맞춰 두었다 |
| 색 | 트루컬러 터미널 |

## 라이선스

사내용입니다. 공개 저장소인 것은 Homebrew 가 tarball 을 받을 수 있게 하려는 것이고
오픈소스로 낸 것이 아닙니다. 자세한 것은 `LICENSE`.
