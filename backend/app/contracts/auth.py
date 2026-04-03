from pydantic import BaseModel


class MockLoginRequest(BaseModel):
    shop_id: str


class MockLoginData(BaseModel):
    access_token: str
    token_type: str
    owner_actor_id: str
    shop_id: str
    shop_name: str
