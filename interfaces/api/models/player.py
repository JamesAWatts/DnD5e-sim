from pydantic import BaseModel

class PlayerCreate(BaseModel):
    name: str
    hp: int

class PlayerResponse(BaseModel):
    id: int
    name: str
    hp: int