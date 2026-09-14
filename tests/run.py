"""검사를 전부 돌린다. 바깥 패키지가 필요 없다.

    python3 tests/run.py              전부
    python3 tests/run.py sprites      이름에 sprites 가 들어간 모듈만
    python3 tests/run.py --quick      몇 초 넘게 걸리는 검사를 뺀다
    python3 tests/run.py --deep       무작위 입력 검사를 스무 배로 돌린다
    python3 tests/run.py -x           처음 실패에서 멈춘다

검사는 `grid.seal` 로 밀폐한 자리에서 돈다. 건너뛴 검사는 까닭과 함께 따로 센다.
환경변수 TESTS_NO_SKIP=1 이면 건너뛴 것도 실패로 센다.
"""
import importlib
import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def main():
    args = sys.argv[1:]
    quick, deep, first = "--quick" in args, "--deep" in args, "-x" in args
    picks = [a for a in args if not a.startswith("-")]
    if deep:
        os.environ["TESTS_DEEP"] = "20"
    no_skip = os.environ.get("TESTS_NO_SKIP") == "1"
    import grid
    grid.seal()

    mods = sorted(f[:-3] for f in os.listdir(HERE)
                  if f.startswith("test_") and f.endswith(".py"))
    if picks and not any(p in m for m in mods for p in picks):
        print(f"고른 이름에 맞는 검사 모듈이 없다: {picks}")
        return 1
    passed, failed, skipped = 0, [], []
    began = time.time()
    for name in mods:
        if picks and not any(p in name for p in picks):
            continue
        mod = importlib.import_module(name)
        cases = sorted(k for k in dir(mod) if k.startswith("test_"))
        print(f"\n{name}  ({len(cases)}건)")
        for case in cases:
            fn = getattr(mod, case)
            label = case[5:].replace("_", " ")
            if quick and getattr(fn, "slow", False):
                skipped.append((name, case, "--quick"))
                print(f"  건너뜀  {label}  (--quick)")
                continue
            start = time.time()
            try:
                fn()
            except grid.Skip as why:
                skipped.append((name, case, str(why)))
                print(f"  건너뜀  {label}  ({why})")
                continue
            except KeyboardInterrupt:
                raise
            except BaseException as e:                 # 검사 안의 sys.exit 도 실패로 센다
                failed.append((name, case, e))
                print(f"  실패  {label}")
                if first:
                    break
            else:
                passed += 1
                took = time.time() - start
                print(f"  통과  {label}" + (f"  {took:.1f}초" if took >= 1 else ""))
        if first and failed:
            break

    print(f"\n{'=' * 60}")
    for name, case, e in failed:
        print(f"\n[{name}.{case}]")
        where = traceback.extract_tb(e.__traceback__)[-1]
        print(f"  {os.path.basename(where.filename)}:{where.lineno}  {where.line}")
        print(f"  {type(e).__name__}: {e}")
    print(f"\n통과 {passed}, 실패 {len(failed)}, 건너뜀 {len(skipped)}  ({time.time() - began:.0f}초)")
    if failed or (no_skip and skipped):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
