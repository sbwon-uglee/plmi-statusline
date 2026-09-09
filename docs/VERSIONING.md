# 버전과 브랜치

`uglee` 저장소와 같은 방식을 쓴다. 다른 저장소를 오가며 규칙이 갈리면 어느 쪽이 맞는지
매번 확인하게 되므로 한 가지로 맞춘다.

## 브랜치

| 이름 | 쓰임 |
|---|---|
| `main` | 낸 것만 있다. 태그가 여기 붙는다 |
| `dev` | 다음 버전에 담을지 안 담을지 아직 모르는 것 |
| `vX.Y.Z` | 그 버전을 만드는 동안 쓰는 작업 브랜치 |

버전 브랜치에서 만들고, 끝나면 `main` 에 넣고 태그를 찍는다.

## 한 버전을 내는 절차

```
git switch -c v0.1.0 main         버전 브랜치를 딴다
echo 0.1.0 > VERSION              chore: VERSION bump to 0.1.0
...                               feat / fix / refactor 커밋들
                                  docs: changelog 0.1.0
git switch main && git merge --ff-only v0.1.0
git tag -a v0.1.0 -m "release v0.1.0"
git branch -d v0.1.0              태그와 이름이 겹치므로 낸 뒤에는 지운다
```

굽는 것이 들어간 버전은 태그 전에 `./build.sh` 가 통과해야 한다. 스프라이트는 저장소에
같이 들어가므로 소스만 고치고 굽지 않으면 받는 사람에게는 안 바뀐 채로 간다.

## 커밋 제목

`유형: 무엇을` 또는 `유형(범위): 무엇을`. 본문은 왜 그렇게 했는지를 적는다.

| 유형 | 쓰는 자리 |
|---|---|
| `feat` | 쓰는 사람이 새로 할 수 있게 된 것 |
| `fix` | 틀린 것을 맞게 |
| `perf` | 같은 결과를 더 빠르거나 작게 |
| `refactor` | 겉보기 동작은 그대로, 구조만 |
| `style` | 문구와 서식 |
| `docs` | 문서만 |
| `chore` | 버전 올리기, 굽기, 설정 |

## VERSION 파일

`VERSION` 하나가 기준이다. brew 포뮬러도 태그도 이 값을 따라간다. 올리는 커밋은 그것만
담아서 되짚을 때 어디서 갈렸는지 바로 보이게 한다.

## CHANGELOG

`CHANGELOG.md` 맨 위에 새 항목을 얹는다. **쓰는 사람이 무엇을 다르게 겪는지**를 적고,
왜 그렇게 만들었는지와 접은 대안은 `docs/DECISIONS.md` 에 둔다. 둘을 섞으면 받는 사람은
자기와 무관한 내부 사정을 읽게 되고, 나중에 우리는 결정 근거를 릴리스 노트에서 찾게 된다.

## brew 로 내보내기

탭은 포뮬러 하나를 담은 공개 저장소다. 이름에 `homebrew-` 접두어가 붙어야 brew 가 알아본다.

```
sbwon-uglee/homebrew-plmi
└── Formula/plmi.rb
```

받는 사람은 이 한 줄이면 된다.

```
brew install sbwon-uglee/plmi/plmi
plmi
```

포뮬러 원본은 `packaging/plmi.rb` 에 둔다. 버전을 낼 때 `url` 의 태그와 `sha256` 을 고쳐
탭 저장소에 올린다.

```
curl -sL https://github.com/sbwon-uglee/plmi-statusline/archive/refs/tags/v0.1.0.tar.gz \
  | shasum -a 256
```

**소스 저장소가 공개여야 한다.** 비공개면 brew 가 tarball 을 못 받아서 받는 사람마다
토큰을 잡아 줘야 하고, 그러면 한 줄 설치가 아니게 된다.

brew 는 파일을 `<prefix>/Cellar/plmi/<버전>/` 에 두고 `<prefix>/opt/plmi` 가 지금 버전을
가리키게 한다. 설정에 적히는 것은 opt 쪽이라 버전을 올려도 상태줄이 안 깨진다
(`install.py` 의 `stable`).
