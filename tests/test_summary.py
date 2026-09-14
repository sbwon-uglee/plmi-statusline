"""도구 호출이 말풍선에서 어떤 문구가 되는지 분기마다 적어 둔 표.

무작위 입력 검사는 문구가 짧고 죽지 않는지만 본다. 어느 도구가 어느 문구로 가는지는 여기서
하나씩 못 박는다.
"""
import os
import sys

import grid

sys.path.insert(0, os.path.join(grid.ROOT, "plmi"))
from summary import NAME, summarize  # noqa: E402

LONG = "x" * (NAME + 10)
CASES = [
    ("Bash", {"description": "검사 돌리기", "command": "python3 run.py"}, "검사 돌리기"),
    ("Bash", {"command": "python3 run.py"}, "python3 run.py"),
    ("Bash", {"description": "", "command": "ls"}, "ls"),
    ("Read", {"file_path": "/a/b/보고서.md"}, "보고서.md 읽는 중"),
    ("NotebookRead", {"file_path": "/a/n.ipynb"}, "n.ipynb 읽는 중"),
    ("Read", {"file_path": "/a/" + LONG}, LONG[:NAME] + " 읽는 중"),
    ("Edit", {"file_path": "/a/b.py"}, "b.py 고치는 중"),
    ("Write", {"file_path": "/a/c.py"}, "c.py 고치는 중"),
    ("NotebookEdit", {"file_path": "/a/n.ipynb"}, "n.ipynb 고치는 중"),
    ("Grep", {"pattern": "TODO"}, "TODO 찾는 중"),
    ("Glob", {"pattern": "*.py"}, "*.py 찾는 중"),
    ("Agent", {"description": "코드 검토"}, "코드 검토 시키는 중"),
    ("Task", {"description": "코드 검토"}, "코드 검토 시키는 중"),
    ("Agent", {"description": ""}, "에이전트 시키는 중"),
    ("Agent", {}, "에이전트 시키는 중"),
    ("WebFetch", {"url": "https://example.com"}, "웹 보는 중"),
    ("WebSearch", {"query": "x"}, "웹 보는 중"),
    ("mcp__google-sheets__get_sheet_data", {}, "시트 여는 중"),
    ("mcp__claude_ai_Slack__slack_read_channel", {}, "슬랙 보는 중"),
    ("mcp__claude_ai_Gmail__search_threads", {}, "메일 보는 중"),
    ("mcp__claude_ai_Notion__notion-fetch", {}, "노션 보는 중"),
    ("mcp__srv__do_thing", {}, "do_thing 부르는 중"),
    ("mcp__srv__" + LONG, {}, LONG[:NAME] + " 부르는 중"),
    ("TodoWrite", {}, "TodoWrite 실행 중"),
    (LONG, {}, LONG[:NAME] + " 실행 중"),
    ("Read", None, " 읽는 중"),
    (None, {"file_path": "/a"}, " 실행 중"),
]


def test_도구마다_말풍선_문구가_표와_같다():
    wrong = [(tool, arg, summarize(tool, arg), want) for tool, arg, want in CASES
             if summarize(tool, arg) != want]
    assert not wrong, "\n".join(f"{t!r} {a!r}: {got!r}, 기대 {w!r}" for t, a, got, w in wrong)
