from pydantic import BaseModel, Field


class PlayerCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)


class PlayerRead(BaseModel):
    id: int
    username: str


class TokenRead(BaseModel):
    access_token: str
    token_type: str = "bearer"
