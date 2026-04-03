from pydantic import BaseModel


class SessionBootstrapData(BaseModel):
    session_id: str
    session_type: str
    title: str
    participants: list[str]
