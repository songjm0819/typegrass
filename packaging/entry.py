"""배포용 .app 의 시작점. 인자 없이 실행(더블클릭)하면 올인원 앱을 켠다."""
import sys

from typegrass.cli import main

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-psn")]  # 예전 macOS 가 붙이는 인자 제거
    raise SystemExit(main(args or ["app"]))
