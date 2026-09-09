"""검사를 전부 돌린다. 바깥 패키지가 필요 없다.

    python3 tests/run.py            전부
    python3 tests/run.py sprites    이름에 sprites 가 들어간 것만

스프라이트를 다시 구운 뒤에는 반드시 돌린다. `plmi/anim.py` 가 끝에서 자동으로 부른다.
"""
import importlib
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def main():
    pick = sys.argv[1] if len(sys.argv) > 1 else ""
    mods = sorted(f[:-3] for f in os.listdir(HERE)
                  if f.startswith("test_") and f.endswith(".py"))
    passed, failed = 0, []
    for name in mods:
        if pick and pick not in name:
            continue
        mod = importlib.import_module(name)
        cases = sorted(k for k in dir(mod) if k.startswith("test_"))
        print(f"\n{name}  ({len(cases)}건)")
        for case in cases:
            try:
                getattr(mod, case)()
            except Exception as e:
                failed.append((name, case, e, traceback.format_exc()))
                print(f"  실패  {case[5:].replace('_', ' ')}")
            else:
                passed += 1
                print(f"  통과  {case[5:].replace('_', ' ')}")

    print(f"\n{'=' * 60}")
    if failed:
        for name, case, e, tb in failed:
            print(f"\n[{name}.{case}]")
            line = [x for x in tb.splitlines() if "assert" in x or "Error" in x]
            print("  " + (line[-1].strip() if line else str(e)))
            print(f"  {type(e).__name__}: {e}")
        print(f"\n통과 {passed} · 실패 {len(failed)}")
        return 1
    print(f"통과 {passed} · 실패 0")
    return 0


if __name__ == "__main__":
    sys.exit(main())
