from pydantic import BaseModel, Field
from typing import Optional, List

class ChatRequest(BaseModel):
    session_id: str = Field(..., example="demo-session-1")
    message: str = Field(..., example="What does sample.pdf say about AI?")

class SourceReference(BaseModel):
    document: str
    snippet: Optional[str] = None

class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceReference] = []
    retrieved_context: Optional[str] = None
    saved_note_id: Optional[int] = None

class NoteResponse(BaseModel):
    id: int
    session_id: str
    title: str
    content: str
    tags: Optional[str] = None

    class Config:
        from_attributes = True  # Allows ORM model conversion