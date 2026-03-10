from __future__ import annotations

from pydantic import BaseModel, Field


class AnnotationBounds(BaseModel):
    x: float
    y: float
    width: float
    height: float


class BrowserInfo(BaseModel):
    user_agent: str
    viewport_width: int
    viewport_height: int
    platform: str


class FeedbackSubmitRequest(BaseModel):
    type: str = Field(..., pattern="^(bug|feature|ux|praise)$")
    description: str = Field(..., min_length=10, max_length=2000)
    page_url: str
    page_title: str | None = None
    screenshot_storage_path: str | None = None
    annotation_bounds: AnnotationBounds | None = None
    browser_info: BrowserInfo | None = None
    console_errors: list[str] | None = None


class FeedbackResponse(BaseModel):
    id: str
    github_issue_url: str | None = None
    message: str
