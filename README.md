# plmi-statusline

Claude Code 의 statusLine 자리에 사는 플밍이. 어글리랩 마스코트를 브라유 점으로 그려서,
지금 Claude 가 무엇을 하고 있는지에 따라 표정과 자세가 바뀐다.

터미널 한 줄이 아니라 여러 줄을 쓴다. 26칸 기준으로 11줄이다.

## 설치

```bash
brew install sbwon-uglee/plmi/plmi
plmi
```

Claude Code 를 다시 띄우면 나온다. 필요한 것은 brew 와 python3 뿐이고, python3 는 맥에
기본으로 들어 있다.

올릴 때는 `brew upgrade plmi`, 뗄 때는 `plmi --uninstall` 뒤에 `brew uninstall plmi`.
순서를 바꿔도 상태줄이 조용히 비기만 하고 오류를 뱉지는 않는다. 다만 설정에 죽은
경로가 남으므로 `plmi --uninstall` 을 먼저 하는 편이 깔끔하다.
설정에 적히는 경로에는 버전이 안 들어가므로 판을 올려도 상태줄이 안 깨진다.

### brew 없이

```bash
git clone https://github.com/sbwon-uglee/plmi-statusline.git ~/.claude/plmi
python3 ~/.claude/plmi/plmi/install.py
```

받는 위치는 아무 데나 되고, 옮기면 `install.py` 를 다시 돌리면 된다. `statusline.py` 가
스프라이트를 자기 파일 기준으로 찾으므로 어느 폴더에서 Claude Code 를 띄우든 그대로 돈다.

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
```

크기는 36x16, 26x11, 20x10, 16x8 네 가지를 구워 둔다. 앞이 칸 수, 뒤가 줄 수다.
창보다 넓은 크기는 붙일 때 막는다. 줄바꿈으로 그림이 무너지기 때문이다.

### 다른 크기로 굽기

```bash
plmi --bake 30       30칸으로 굽는다
plmi --size 30x13    구운 것으로 갈아 낀다
```

줄 수는 굽고 나서 정해지므로 칸 수만 준다. 결과는 `~/.claude/plmi-sizes` 에 들어가고
판을 올려도 살아남는다. 굽는 데는 numpy 와 pillow 가 필요하다. `uv` 가 있으면 그때만
받아 쓰고, 없으면 이미 깔린 것을 쓴다.

### 환경변수

| 이름 | 기본 | 하는 일 |
|---|---|---|
| `PLMI_SIZE` | 26칸에 가장 가까운 것 | 쓸 크기 |
| `PLMI_BUBBLE` | `1` | 말풍선. `0` 이면 그림만 |
| `PLMI_COLOR` | `1` | 색. `0` 이면 흑백 |

설치기가 `PLMI_SIZE` 를 설정에 넣어 준다. 나머지는 필요하면 그 명령 앞에 붙인다.

### 상태

| 상태 | 언제 | 말풍선 |
|---|---|---|
| 숨쉬기 | 아무 일 없을 때 | |
| 작업중 | 도구를 쓰는 중 | 하는 일 한 줄 |
| 생각중 | 사람 말을 받았거나 생각하는 중 | 무슨 일인지 보는 중, 생각하는 중 |
| 승인대기 | 도구 호출 뒤 4초 넘게 결과가 안 올 때 | 하는 일 한 줄 |
| 완료 | 답을 마친 뒤 4초 동안 | 끝 |
| 오류 | 도구가 실패했을 때 | 안 됐어 |
| 놀람 | 하던 일을 사람이 끊었을 때 | 앗 |
| 뾰로통 | 15분 넘게 아무 일이 없을 때. 눈은 뜬 채 입만 시무룩하다 | 심심해 |

말풍선은 일이 난 순간 문구가 한꺼번에 뜨고 뒤에서 점이 하나씩 는다. 심심해와 안 됐어는
점이 세 개까지 차면 3초 쉬었다가 다시 뜨고, 앗과 끝은 한 번만 뜬다. 일하는 중 문구는
사라지지 않고 점만 계속 돈다. 상자는 점이 다 찼을 때 크기로 잡으므로 점이 느는 동안 그림이
밀리지 않는다.

설치기는 `~/.claude/settings.json` 의 `statusLine` 만 건드리고 나머지 설정은 그대로 둔다.
쓰기 전에 백업을 뜨고, 플밍이가 아닌 statusLine 이 이미 있으면 `--force` 없이는 덮지 않는다.

## 창으로 띄우기

statusLine 말고 창 하나를 통째로 쓰고 싶으면 `플밍이창.command` 를 더블클릭한다.
statusLine 은 Claude Code 가 다시 그려 줄 때만 움직이는데, 이쪽은 12fps 로 자기가 그린다.

## 상태 반영

훅을 쓰지 않는다. Claude Code 가 statusLine 명령에 stdin 으로 넘겨 주는 세션 JSON 에
`transcript_path` 가 들어 있어서, 그 파일 끝을 읽어 지금 무슨 일이 벌어지는지 알아낸다.
끝 32KB 부터 읽고, 도구 결과 한 줄이 그보다 커서 판정할 것이 모자라면 2MB 까지 넓혀 가며
다시 읽는다. 말풍선 박자도 이 기록에 적힌 사건 시각에 맞춘다.

훅으로 하면 도구 호출마다 프로세스가 끼어들고 UserPromptSubmit 훅은 출력이 대화에 실려
토큰을 먹는다. statusLine 은 화면에만 찍혀서 대화에 아무것도 남기지 않는다.

## 구조

```
plmi/
  statusline.py     statusLine 진입점. 표준 라이브러리만 쓴다
  bubble.py         말풍선
  summary.py        도구 호출을 한 줄 한국어로
  state.py          수동 상태 덮어쓰기
  play.py           터미널에서 재생해 보는 도구
  install.py        settings.json 에 붙이고 뗀다
  anim.py           스프라이트를 굽는다. numpy 와 pillow 가 필요하다
  dot.py            점 그림 엔진
  sprite.py         브라유 인코딩
  build_sprites.py  정지 그림
  dump_frames.py    전 프레임을 HTML 로
  sprites/anim/     구워 둔 스프라이트 JSON. 8상태 x 4크기
assets/             원화 PNG. 굽는 데만 쓴다
플밍이창.command     창 하나로 띄우는 실행기. 더블클릭
build.sh            다시 굽고 검사까지
tests/              검사와 돌연변이
```

실행에는 `sprites/anim` 의 JSON 과 표준 라이브러리만 있으면 된다.
`assets` 와 numpy, pillow 는 스프라이트를 다시 구울 때만 쓴다.

## 고쳐 쓰기

```bash
./build.sh              네 크기 전부 다시 굽고 검사까지
./build.sh 36 26        고른 크기만
```

크기를 바꾸려면 인자로 칸 수를 준다. 줄 수는 자동으로 잡는다.
`build.sh` 는 옛 스프라이트를 먼저 지우고, 다 구운 뒤 `tests/` 를 돌린다.
검사가 하나라도 깨지면 거기서 멈춘다.
표정을 바꾸려면 `plmi/dot.py` 의 `EYE_ART` 와 `MOUTH_ART` 에 점 패턴을 고치거나 더한다.

굽고 나서 눈으로 확인하려면 전 프레임을 HTML 로 뽑는다.

```bash
uv run --with numpy --with pillow python plmi/dump_frames.py
```

크기를 바꿔 구우면 결과 파일 이름의 줄 수가 달라진다. `build.sh` 가 굽기 전에
옛 파일을 지운다. `anim.py` 를 직접 부를 때는 손으로 지워야 한다.

## 검사

```bash
python3 tests/run.py            전부
python3 tests/run.py sprites    이름에 sprites 가 들어간 것만
python3 tests/mutate.py         검사가 실제로 잡는지 본다
```

스프라이트가 지켜야 하는 것(좌우 대칭, 볼 자리, 머리 잘림, 프레임 중복, 아래 여백),
실행 쪽이 지켜야 하는 것(표준 라이브러리만, 크기별 줄 수, 배경색 안 씀, 기록에서 상태 읽기,
말풍선 박자), 설치기가 지켜야 하는 것(남의 설정을 안 건드림, 절대경로, 백업, 떼는 순서),
글쓰기 규칙(이모지, em dash, 코드에 적은 변경 이력)을 본다.

검사마다 왜 있는지는 그 검사의 설명 문자열에 있고, 접은 대안은 `docs/DECISIONS.md`.

`mutate.py` 는 검사가 막는 결함을 하나씩 일부러 넣어 보고 그 검사가 실패하는지 본다.
통과만 하는 검사는 없느니만 못하므로, 검사를 고치거나 더할 때 여기도 같이 늘린다.

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
