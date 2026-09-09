"""도구 호출을 말풍선 한 줄로 줄인다.

훅이 아니라 statusline 이 부른다. 트랜스크립트에서 읽은 도구 이름과 인자를 그대로 넘긴다.
"""
import os

MAX = 22                                      # 말풍선 한 줄에 들어가는 대략의 칸 수


def base(p):
    return os.path.basename(str(p).rstrip("/")) or str(p)


def summarize(tool, arg):
    """도구 호출을 사람 말로 줄인다. Bash 는 도구가 준 description 이 이미 요약이다."""
    arg = arg or {}
    if tool == "Bash":
        return arg.get("description") or str(arg.get("command", ""))[:MAX]
    if tool in ("Read", "NotebookRead"):
        return f"{base(arg.get('file_path', ''))} 읽는 중"
    if tool in ("Edit", "Write", "NotebookEdit"):
        return f"{base(arg.get('file_path', ''))} 고치는 중"
    if tool in ("Grep", "Glob"):
        return f"{str(arg.get('pattern', ''))[:14]} 찾는 중"
    if tool == "Task":
        return f"{arg.get('description', '에이전트')} 시키는 중"
    if tool in ("WebFetch", "WebSearch"):
        return "웹 보는 중"
    if tool.startswith("mcp__google-sheets"):
        return "시트 여는 중"
    if tool.startswith("mcp__claude_ai_Slack"):
        return "슬랙 보는 중"
    if tool.startswith("mcp__claude_ai_Gmail"):
        return "메일 보는 중"
    if tool.startswith("mcp__claude_ai_Notion"):
        return "노션 보는 중"
    if tool.startswith("mcp__"):
        return tool.split("__")[-1][:MAX] + " 부르는 중"
    return f"{tool} 실행 중"
