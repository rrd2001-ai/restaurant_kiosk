from pydantic import BaseModel, Field

class SessionStart(BaseModel):
    customer_name: str | None = Field(default=None, max_length=80)

class ConversationRequest(BaseModel):
    session_id: str
    text: str = Field(min_length=1, max_length=1000)

class CartRequest(BaseModel):
    session_id: str
    item_id: str
    quantity: int = Field(default=1, ge=1, le=99)

class CustomerRequest(BaseModel):
    session_id: str
    name: str = Field(min_length=1, max_length=80)
    phone: str | None = Field(default=None, max_length=20)
