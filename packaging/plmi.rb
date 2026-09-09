# 이 파일의 사본이 탭 저장소 `sbwon-uglee/homebrew-plmi` 의 `Formula/plmi.rb` 로 간다.
# 여기 두는 것은 원본이고, 버전을 낼 때 url 과 sha256 을 고쳐 탭에 올린다.
#
#   받는 사람:  brew install sbwon-uglee/plmi/plmi
#              plmi --size 26x11
#
# sha256 은 이렇게 구한다.
#   curl -sL https://github.com/sbwon-uglee/plmi-statusline/archive/refs/tags/v0.1.0.tar.gz | shasum -a 256
class Plmi < Formula
  desc "Claude Code 상태줄에 사는 도트 캐릭터 플밍이"
  homepage "https://github.com/sbwon-uglee/plmi-statusline"
  url "https://github.com/sbwon-uglee/plmi-statusline/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "0" * 64
  license "MIT"

  # 상태줄을 그리는 쪽은 표준 라이브러리만 쓴다. 맥 기본 파이썬으로 충분하다
  depends_on "python@3" => :test

  def install
    libexec.install "plmi", "VERSION", "README.md", "CHANGELOG.md"
    bin.install_symlink libexec/"plmi/install.py" => "plmi"
  end

  def caveats
    <<~TEXT
      상태줄에 붙이려면 한 번 실행합니다.

          plmi

      크기를 고르려면 `plmi --size 36x16`, 떼려면 `plmi --uninstall` 입니다.
      설정에는 #{opt_prefix} 아래 경로가 적히므로 버전을 올려도 깨지지 않습니다.
    TEXT
  end

  test do
    assert_match version.to_s, shell_output("#{bin}/plmi --version")
    # 설정을 건드리지 않고 쓸 내용만 확인한다
    system bin/"plmi", "--scope", "project", "--dry-run"
  end
end
