"""도구 호출을 말풍선 문구로 줄인다. statusline 이 대화 기록에서 읽은 도구 이름과 인자를 넘긴다."""
import os

NAME = 16     # 파일, 패턴, 도구 이름을 자르는 글자 수. 뒤에 붙는 「 고치는 중」까지 말풍선 문구 22자 안에 든다


def base(p):
    return os.path.basename(str(p).rstrip("/")) or str(p)


def summarize(tool, arg):
    """도구 호출을 사람 말로 줄인다. Bash 는 도구가 준 description 이 이미 요약이다.

    대화 기록에서 읽은 값이라 이름이 문자열이 아니거나 인자가 dict 가 아니어도 문구를 낸다.
    """
    tool = tool if isinstance(tool, str) else ""
    arg = arg if isinstance(arg, dict) else {}

    def field(key, empty=""):
        v = arg.get(key)
        return empty if v is None or v == "" else str(v)

    if tool == "Bash":
        return field("description") or field("command")
    if tool in ("Read", "NotebookRead"):
        return f"{base(field('file_path'))[:NAME]} 읽는 중"
    if tool in ("Edit", "Write", "NotebookEdit"):
        return f"{base(field('file_path'))[:NAME]} 고치는 중"
    if tool in ("Grep", "Glob"):
        return f"{field('pattern')[:NAME]} 찾는 중"
    if tool in ("Agent", "Task"):
        return f"{field('description', '에이전트')[:NAME]} 시키는 중"
    if tool in ("WebFetch", "WebSearch"):
        return "웹 보는 중"
    if tool.startswith("mcp__google-sheets__"):
        return "시트 여는 중"
    if tool.startswith("mcp__claude_ai_Slack__"):
        return "슬랙 보는 중"
    if tool.startswith("mcp__claude_ai_Gmail__"):
        return "메일 보는 중"
    if tool.startswith("mcp__claude_ai_Notion__"):
        return "노션 보는 중"
    if tool.startswith("mcp__"):
        return tool.split("__")[-1][:NAME] + " 부르는 중"
    return f"{tool[:NAME]} 실행 중"
