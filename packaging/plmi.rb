# 이 파일의 사본이 탭 저장소 `sbwon-uglee/homebrew-plmi` 의 `Formula/plmi.rb` 로 간다.
# 여기가 원본이고, 버전을 낼 때 url 의 태그와 sha256 을 고쳐 탭에 옮긴다.
#
#   받는 사람:  brew install sbwon-uglee/plmi/plmi
#              plmi
#
# sha256 은 이렇게 구한다.
#   curl -sL https://github.com/sbwon-uglee/plmi-statusline/archive/refs/tags/v0.2.0.tar.gz | shasum -a 256
class Plmi < Formula
  desc "Claude Code 상태줄에 사는 도트 캐릭터 플밍이"
  homepage "https://github.com/sbwon-uglee/plmi-statusline"
  url "https://github.com/sbwon-uglee/plmi-statusline/archive/refs/tags/v0.2.0.tar.gz"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000"

  # 파이썬은 의존으로 걸지 않는다. 상태줄을 그리는 쪽이 표준 라이브러리만 써서 맥에 이미
  # 있는 python3 로 충분하고, 걸어 두면 쓰지도 않을 파이썬을 통째로 받게 된다.

  def install
    # assets 는 손수 굽는 데 쓴다(plmi --bake). 빼면 구울 원화가 없다
    libexec.install "plmi", "assets", "VERSION"
    # install.py 에는 셰뱅이 없다. 심볼릭 링크로 걸면 셸이 실행할 방법을 모른다.
    # 여는 껍데기를 따로 쓴다. 경로는 버전이 안 박힌 opt 쪽이라 판을 올려도 그대로다
    (bin/"plmi").write <<~SH
      #!/bin/bash
      exec python3 "#{opt_libexec}/plmi/install.py" "$@"
    SH
  end

  def caveats
    <<~TEXT
      상태줄에 붙이려면 한 번 실행합니다.

          plmi

      크기를 고르려면 `plmi --size 36x16`, 떼려면 `plmi --uninstall` 입니다.
      설정에는 #{opt_prefix} 아래 경로가 적히므로 판을 올려도 깨지지 않습니다.
    TEXT
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/plmi --version")
    # 설정을 건드리지 않고 쓸 내용만 확인한다
    system bin/"plmi", "--scope", "project", "--dry-run"
  end
end
