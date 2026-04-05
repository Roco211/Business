from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginData(BaseModel):
    access_token: str
    token_type: str
    owner_actor_id: str
    shop_id: str
    shop_name: str


class MockLoginRequest(BaseModel):
    shop_id: str | None = None


class MockLoginData(BaseModel):
    access_token: str
    token_type: str
    owner_actor_id: str
    shop_id: str
    shop_name: str
