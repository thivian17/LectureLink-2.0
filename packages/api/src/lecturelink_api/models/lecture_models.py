from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Lecture Processing Models
# ---------------------------------------------------------------------------

class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str
    speaker: str = "professor"

class RouteResult(BaseModel):
    processing_path: str  # 'audio_only', 'slides_only', 'audio+slides'
    audio_url: str | None = None
    slides_url: str | None = None
    estimated_duration: int | None = None  # seconds

class SlideAnalysis(BaseModel):
    slide_number: int
    title: str | None = None
    text_content: str
    visual_description: str | None = None
    has_diagram: bool = False
    has_code: bool = False
    has_equation: bool = False

class AlignedSegment(BaseModel):
    start: float | None = None
    end: float | None = None
    text: str
    speaker: str = "professor"
    slide_number: int | None = None
    source: str  # 'audio', 'slide', 'aligned'

class ExtractedConcept(BaseModel):
    title: str
    description: str
    category: str  # 'definition', 'theorem', 'process', 'concept', 'example', 'formula'
    difficulty_estimate: float = 0.5
    related_concepts: list[str] = []
    embedding: list[float] | None = None  # 768-dim vector
    source_chunk_ids: list[str] = []  # Populated by Concept-Chunk Linker

class LectureChunk(BaseModel):
    chunk_index: int
    content: str
    start_time: float | None = None
    end_time: float | None = None
    slide_number: int | None = None
    embedding: list[float] | None = None  # 768-dim vector
    metadata: dict = {}  # {source: 'audio'|'slide'|'aligned', speaker: '...'}