import ara_sdk as ara

from tools.transcribe import transcribe

@ara.tool
def utc_now() -> dict:
    from datetime import datetime, timezone
    return {"utc_time": datetime.now(timezone.utc).isoformat()}

ara.Automation(
    "hello-hourly-agent",
    system_instructions=(
        "Reply with one short hello message and include UTC time. "
        "Use transcribe first when available. "
        "Only include transcribed input text when transcribe returns ok=true. "
        "If linq_send_message is available and a phone route is paired, "
        "send the same message there once."
    ),
    tools=[utc_now, transcribe],
)
