from pydantic import BaseModel, ConfigDict


class KeyCreate(BaseModel):
    name: str  # 例如 "team-a" 或 "john-dev"
    description: str = ""


class KeyInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    name: str
    description: str
    created_at: str
    is_active: int
    total_requests: int
    total_tokens: int
    total_cost_usd: float
