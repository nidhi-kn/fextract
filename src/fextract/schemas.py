"""Validated output models shared by the extraction pipeline."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class FieldValue(BaseModel):
    """One extracted value with confidence, provenance, and review metadata."""

    value: Any | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    page: int | None = None
    bbox: list[float] | None = None
    source: Literal["rule", "llm", "vlm", "derived", "none"] = "none"
    source_layer: str | None = None
    null_reason: Literal["not_present", "unreadable", "ambiguous"] | None = None
    flags: list[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    """Outcome of one arithmetic or structural validation check."""

    check: str
    passed: bool | None
    detail: str | None = None
    status: Literal["passed", "failed", "not_evaluable"] | None = None

    def model_post_init(self, __context: Any) -> None:
        """Expose a readable status alongside the backwards-compatible boolean."""
        if self.status is None:
            self.status = (
                "not_evaluable"
                if self.passed is None
                else "passed" if self.passed else "failed"
            )


class SectionResult(BaseModel):
    """Extraction result for a consecutive page section."""

    doc_type: str
    doc_type_confidence: float
    pages: list[int]
    fields: dict[str, FieldValue]
    tables: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    validation: list[ValidationResult] = Field(default_factory=list)


class DocumentResult(BaseModel):
    """Machine-readable result for one source document."""

    source_file: str
    page_count: int
    extraction_paths: dict[int, str]
    source_quality: dict[int, dict[str, float]] = Field(default_factory=dict)
    sections: list[SectionResult]
    cross_section_validation: list[ValidationResult] = Field(default_factory=list)
    needs_review: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    timings_ms: dict[str, float] = Field(default_factory=dict)
