from dataclasses import dataclass, field


@dataclass
class Session:
    system_prompt: str
    messages: list[dict] = field(default_factory=list)


_sessions: dict[int, Session] = {}


def start_session(channel_id: int, system_prompt: str) -> Session:
    session = Session(system_prompt=system_prompt)
    _sessions[channel_id] = session
    return session


def get_session(channel_id: int) -> Session | None:
    return _sessions.get(channel_id)


def end_session(channel_id: int) -> Session | None:
    return _sessions.pop(channel_id, None)
