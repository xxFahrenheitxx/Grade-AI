"""Multi-provider AI client wrapper for AI grading."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, Optional, TYPE_CHECKING

from pydantic import BaseModel

from gradeai.constants import AI_MAX_TOKENS

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    import anthropic  # noqa: F401
    import google.generativeai as genai  # noqa: F401
    import openai  # noqa: F401


def _pydantic_to_tool(name: str, description: str, model_class: type[BaseModel]) -> dict:
    """Convert a Pydantic model to an Anthropic tool definition."""
    return {
        "name": name,
        "description": description,
        "input_schema": model_class.model_json_schema(),
    }


def _make_schema_strict(schema: dict) -> dict:
    """Add additionalProperties: false to all objects in a JSON schema for OpenAI strict mode."""
    if isinstance(schema, dict):
        # If this is a structured object type, add additionalProperties: false
        if schema.get("type") == "object":
            # OpenAI strict JSON schema requires `required` to include every key in `properties`.
            properties = schema.get("properties")
            if isinstance(properties, dict):
                schema["additionalProperties"] = False
                schema["required"] = sorted(properties.keys())

        # Recursively process all nested schemas
        for key, value in schema.items():
            if isinstance(value, dict):
                _make_schema_strict(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        _make_schema_strict(item)

    return schema


# --- Pydantic response schemas for structured output ---

class CriterionResponse(BaseModel):
    """A single evaluation criterion from AI grading."""
    description: str
    points_awarded: float
    feedback: str


class AnnotationResponse(BaseModel):
    """An annotation placed on the exam document."""
    page: int
    x: float
    y: float
    width: float
    height: float
    text: str
    annotation_type: str  # "highlight", "comment", "correction", "checkmark", "cross"
    question_number: int


class QuestionResponse(BaseModel):
    """Grading result for a single question."""
    question_title: str
    question_number: int
    criteria: list[CriterionResponse]
    points_possible: Optional[float] = None


class GradingResponse(BaseModel):
    """Complete AI grading response."""
    student_name: Optional[str] = None
    questions: list[QuestionResponse]
    annotations: list[AnnotationResponse]
    overall_feedback: str
    total_points_possible: Optional[float] = None


class QuestionDetectionItem(BaseModel):
    """A detected question from an exam."""
    question_title: str
    question_number: int
    points_possible: Optional[float] = None
    answer_summary: str = ""


class QuestionDetectionResponse(BaseModel):
    """Response for question detection."""
    questions: list[QuestionDetectionItem]


class PointDetectionItem(BaseModel):
    """Point allocation for a question."""
    question_number: int
    question_title: str
    points_possible: Optional[float] = None


class PointDetectionResponse(BaseModel):
    """Response for point detection."""
    questions: list[PointDetectionItem]
    total_points: Optional[float] = None


class GradeCalculationResponse(BaseModel):
    """Response for final grade calculation."""
    grade: str


class ExamPaperQuestionItem(BaseModel):
    """A question extracted from a blank exam paper."""
    question_title: str
    question_number: int
    points_possible: Optional[float] = None
    question_text: str = ""


class ExamPaperAnalysisResponse(BaseModel):
    """Response from exam paper analysis."""
    questions: list[ExamPaperQuestionItem]
    total_points: Optional[float] = None


class ExamMatchingResponse(BaseModel):
    """Response from exam-to-paper matching."""
    matched_template_index: Optional[int] = None
    confidence: float = 0.0
    reasoning: str = ""


class AIClient:
    """Multi-provider AI client for exam grading."""

    def __init__(self, api_key: str, provider: str = "anthropic", model: str = "claude-sonnet-4-6") -> None:
        self.api_key = api_key
        self.provider = provider
        self.model = model

        # Initialize provider-specific clients
        if provider == "anthropic":
            try:
                import anthropic
            except ImportError as exc:
                raise ImportError("Missing dependency: install `anthropic` to use provider='anthropic'.") from exc
            self.anthropic_client = anthropic.Anthropic(api_key=api_key)
        elif provider == "openai":
            try:
                import openai
            except ImportError as exc:
                raise ImportError("Missing dependency: install `openai` to use provider='openai'.") from exc
            self.openai_client = openai.OpenAI(api_key=api_key)
        elif provider == "google":
            try:
                import google.generativeai as genai
            except ImportError as exc:
                raise ImportError(
                    "Missing dependency: install `google-generativeai` to use provider='google'."
                ) from exc
            genai.configure(api_key=api_key)
            self._genai = genai

    def grade_exam(
        self,
        system_prompt: str,
        content_blocks: list[dict[str, Any]],
    ) -> GradingResponse:
        """Run AI grading and return structured response.

        Args:
            system_prompt: The system prompt for grading instructions.
            content_blocks: Multi-modal content (text + images) for the user message.

        Returns:
            Parsed GradingResponse with questions, criteria, and annotations.
        """
        logger.info("Starting AI grading with provider %s, model %s", self.provider, self.model)

        if self.provider == "anthropic":
            return self._grade_exam_anthropic(system_prompt, content_blocks)
        elif self.provider == "openai":
            return self._grade_exam_openai(system_prompt, content_blocks)
        elif self.provider == "google":
            return self._grade_exam_google(system_prompt, content_blocks)
        else:
            raise ValueError(f"Unsupported AI provider: {self.provider}")

    def _grade_exam_anthropic(
        self,
        system_prompt: str,
        content_blocks: list[dict[str, Any]],
    ) -> GradingResponse:
        """Grade exam using Anthropic API."""
        tool_def = _pydantic_to_tool(
            "grading_response",
            "Submit the structured grading results for the exam.",
            GradingResponse,
        )

        response = self.anthropic_client.messages.create(
            model=self.model,
            max_tokens=AI_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": content_blocks}],
            tools=[tool_def],
            tool_choice={"type": "tool", "name": "grading_response"},
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "grading_response":
                return GradingResponse.model_validate(block.input)

        raise ValueError("AI response did not contain expected grading_response tool use")

    def _grade_exam_openai(
        self,
        system_prompt: str,
        content_blocks: list[dict[str, Any]],
    ) -> GradingResponse:
        """Grade exam using OpenAI API."""
        # Convert Anthropic-style content blocks to OpenAI format
        openai_content = self._convert_content_to_openai(content_blocks)

        # Get schema and make it strict-mode compatible
        schema = _make_schema_strict(GradingResponse.model_json_schema())

        response = self.openai_client.chat.completions.create(
            model=self.model,
            max_completion_tokens=AI_MAX_TOKENS,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": openai_content},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "grading_response",
                    "strict": True,
                    "schema": schema,
                },
            },
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("OpenAI response did not contain content")

        return GradingResponse.model_validate_json(content)

    def _grade_exam_google(
        self,
        system_prompt: str,
        content_blocks: list[dict[str, Any]],
    ) -> GradingResponse:
        """Grade exam using Google Gemini API."""
        # Convert content blocks to Google format
        google_parts = self._convert_content_to_google(content_blocks)

        model = self._genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system_prompt,
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": GradingResponse.model_json_schema(),
            },
        )

        response = model.generate_content(google_parts)

        if not response.text:
            raise ValueError("Google AI response did not contain content")

        return GradingResponse.model_validate_json(response.text)

    def detect_questions(
        self,
        system_prompt: str,
        content_blocks: list[dict[str, Any]],
    ) -> QuestionDetectionResponse:
        """Detect questions in an exam document."""
        logger.info("Detecting questions with provider %s, model %s", self.provider, self.model)

        if self.provider == "anthropic":
            return self._detect_questions_anthropic(system_prompt, content_blocks)
        elif self.provider == "openai":
            return self._detect_questions_openai(system_prompt, content_blocks)
        elif self.provider == "google":
            return self._detect_questions_google(system_prompt, content_blocks)
        else:
            raise ValueError(f"Unsupported AI provider: {self.provider}")

    def _detect_questions_anthropic(
        self,
        system_prompt: str,
        content_blocks: list[dict[str, Any]],
    ) -> QuestionDetectionResponse:
        """Detect questions using Anthropic API."""
        tool_def = _pydantic_to_tool(
            "question_detection_response",
            "Submit the detected questions found in the exam document.",
            QuestionDetectionResponse,
        )

        response = self.anthropic_client.messages.create(
            model=self.model,
            max_tokens=AI_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": content_blocks}],
            tools=[tool_def],
            tool_choice={"type": "tool", "name": "question_detection_response"},
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "question_detection_response":
                return QuestionDetectionResponse.model_validate(block.input)

        raise ValueError("AI response did not contain expected question_detection_response tool use")

    def _detect_questions_openai(
        self,
        system_prompt: str,
        content_blocks: list[dict[str, Any]],
    ) -> QuestionDetectionResponse:
        """Detect questions using OpenAI API."""
        openai_content = self._convert_content_to_openai(content_blocks)

        # Get schema and make it strict-mode compatible
        schema = _make_schema_strict(QuestionDetectionResponse.model_json_schema())

        response = self.openai_client.chat.completions.create(
            model=self.model,
            max_completion_tokens=AI_MAX_TOKENS,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": openai_content},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "question_detection_response",
                    "strict": True,
                    "schema": schema,
                },
            },
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("OpenAI response did not contain content")

        return QuestionDetectionResponse.model_validate_json(content)

    def _detect_questions_google(
        self,
        system_prompt: str,
        content_blocks: list[dict[str, Any]],
    ) -> QuestionDetectionResponse:
        """Detect questions using Google Gemini API."""
        google_parts = self._convert_content_to_google(content_blocks)

        model = self._genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system_prompt,
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": QuestionDetectionResponse.model_json_schema(),
            },
        )

        response = model.generate_content(google_parts)

        if not response.text:
            raise ValueError("Google AI response did not contain content")

        return QuestionDetectionResponse.model_validate_json(response.text)

    def detect_points(
        self,
        system_prompt: str,
        content_blocks: list[dict[str, Any]],
    ) -> PointDetectionResponse:
        """Detect point allocations from exam/solution/rule documents."""
        logger.info("Detecting point allocations with provider %s, model %s", self.provider, self.model)

        if self.provider == "anthropic":
            return self._detect_points_anthropic(system_prompt, content_blocks)
        elif self.provider == "openai":
            return self._detect_points_openai(system_prompt, content_blocks)
        elif self.provider == "google":
            return self._detect_points_google(system_prompt, content_blocks)
        else:
            raise ValueError(f"Unsupported AI provider: {self.provider}")

    def _detect_points_anthropic(
        self,
        system_prompt: str,
        content_blocks: list[dict[str, Any]],
    ) -> PointDetectionResponse:
        """Detect points using Anthropic API."""
        tool_def = _pydantic_to_tool(
            "point_detection_response",
            "Submit the detected point allocations for exam questions.",
            PointDetectionResponse,
        )

        response = self.anthropic_client.messages.create(
            model=self.model,
            max_tokens=AI_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": content_blocks}],
            tools=[tool_def],
            tool_choice={"type": "tool", "name": "point_detection_response"},
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "point_detection_response":
                return PointDetectionResponse.model_validate(block.input)

        raise ValueError("AI response did not contain expected point_detection_response tool use")

    def _detect_points_openai(
        self,
        system_prompt: str,
        content_blocks: list[dict[str, Any]],
    ) -> PointDetectionResponse:
        """Detect points using OpenAI API."""
        openai_content = self._convert_content_to_openai(content_blocks)

        # Get schema and make it strict-mode compatible
        schema = _make_schema_strict(PointDetectionResponse.model_json_schema())

        response = self.openai_client.chat.completions.create(
            model=self.model,
            max_completion_tokens=AI_MAX_TOKENS,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": openai_content},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "point_detection_response",
                    "strict": True,
                    "schema": schema,
                },
            },
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("OpenAI response did not contain content")

        return PointDetectionResponse.model_validate_json(content)

    def _detect_points_google(
        self,
        system_prompt: str,
        content_blocks: list[dict[str, Any]],
    ) -> PointDetectionResponse:
        """Detect points using Google Gemini API."""
        google_parts = self._convert_content_to_google(content_blocks)

        model = self._genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system_prompt,
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": PointDetectionResponse.model_json_schema(),
            },
        )

        response = model.generate_content(google_parts)

        if not response.text:
            raise ValueError("Google AI response did not contain content")

        return PointDetectionResponse.model_validate_json(response.text)

    def calculate_grade(
        self,
        system_prompt: str,
        content_blocks: list[dict[str, Any]],
    ) -> str:
        """Calculate final grade from grading report + rules."""
        logger.info("Calculating grade with provider %s, model %s", self.provider, self.model)

        if self.provider == "anthropic":
            return self._calculate_grade_anthropic(system_prompt, content_blocks)
        elif self.provider == "openai":
            return self._calculate_grade_openai(system_prompt, content_blocks)
        elif self.provider == "google":
            return self._calculate_grade_google(system_prompt, content_blocks)
        else:
            raise ValueError(f"Unsupported AI provider: {self.provider}")

    def _calculate_grade_anthropic(
        self,
        system_prompt: str,
        content_blocks: list[dict[str, Any]],
    ) -> str:
        tool_def = _pydantic_to_tool(
            "grade_calculation_response",
            "Submit the final grade value for the exam.",
            GradeCalculationResponse,
        )

        response = self.anthropic_client.messages.create(
            model=self.model,
            max_tokens=AI_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": content_blocks}],
            tools=[tool_def],
            tool_choice={"type": "tool", "name": "grade_calculation_response"},
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "grade_calculation_response":
                return GradeCalculationResponse.model_validate(block.input).grade

        raise ValueError("AI response did not contain expected grade_calculation_response tool use")

    def _calculate_grade_openai(
        self,
        system_prompt: str,
        content_blocks: list[dict[str, Any]],
    ) -> str:
        openai_content = self._convert_content_to_openai(content_blocks)
        schema = _make_schema_strict(GradeCalculationResponse.model_json_schema())

        response = self.openai_client.chat.completions.create(
            model=self.model,
            max_completion_tokens=AI_MAX_TOKENS,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": openai_content},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "grade_calculation_response",
                    "strict": True,
                    "schema": schema,
                },
            },
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("OpenAI response did not contain content")
        return GradeCalculationResponse.model_validate_json(content).grade

    def _calculate_grade_google(
        self,
        system_prompt: str,
        content_blocks: list[dict[str, Any]],
    ) -> str:
        google_parts = self._convert_content_to_google(content_blocks)

        model = self._genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system_prompt,
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": GradeCalculationResponse.model_json_schema(),
            },
        )

        response = model.generate_content(google_parts)
        if not response.text:
            raise ValueError("Google AI response did not contain content")
        return GradeCalculationResponse.model_validate_json(response.text).grade

    # ------------------------------------------------------------------
    # Exam paper analysis
    # ------------------------------------------------------------------

    def analyze_exam_paper(
        self,
        system_prompt: str,
        content_blocks: list[dict[str, Any]],
    ) -> ExamPaperAnalysisResponse:
        """Analyze a blank exam paper to extract questions with full text."""
        logger.info("Analyzing exam paper with provider %s, model %s", self.provider, self.model)

        if self.provider == "anthropic":
            return self._analyze_exam_paper_anthropic(system_prompt, content_blocks)
        elif self.provider == "openai":
            return self._analyze_exam_paper_openai(system_prompt, content_blocks)
        elif self.provider == "google":
            return self._analyze_exam_paper_google(system_prompt, content_blocks)
        else:
            raise ValueError(f"Unsupported AI provider: {self.provider}")

    def _analyze_exam_paper_anthropic(
        self,
        system_prompt: str,
        content_blocks: list[dict[str, Any]],
    ) -> ExamPaperAnalysisResponse:
        tool_def = _pydantic_to_tool(
            "exam_paper_analysis_response",
            "Submit the questions extracted from the blank exam paper.",
            ExamPaperAnalysisResponse,
        )

        response = self.anthropic_client.messages.create(
            model=self.model,
            max_tokens=AI_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": content_blocks}],
            tools=[tool_def],
            tool_choice={"type": "tool", "name": "exam_paper_analysis_response"},
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "exam_paper_analysis_response":
                return ExamPaperAnalysisResponse.model_validate(block.input)

        raise ValueError("AI response did not contain expected exam_paper_analysis_response tool use")

    def _analyze_exam_paper_openai(
        self,
        system_prompt: str,
        content_blocks: list[dict[str, Any]],
    ) -> ExamPaperAnalysisResponse:
        openai_content = self._convert_content_to_openai(content_blocks)
        schema = _make_schema_strict(ExamPaperAnalysisResponse.model_json_schema())

        response = self.openai_client.chat.completions.create(
            model=self.model,
            max_completion_tokens=AI_MAX_TOKENS,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": openai_content},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "exam_paper_analysis_response",
                    "strict": True,
                    "schema": schema,
                },
            },
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("OpenAI response did not contain content")
        return ExamPaperAnalysisResponse.model_validate_json(content)

    def _analyze_exam_paper_google(
        self,
        system_prompt: str,
        content_blocks: list[dict[str, Any]],
    ) -> ExamPaperAnalysisResponse:
        google_parts = self._convert_content_to_google(content_blocks)

        model = self._genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system_prompt,
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": ExamPaperAnalysisResponse.model_json_schema(),
            },
        )

        response = model.generate_content(google_parts)
        if not response.text:
            raise ValueError("Google AI response did not contain content")
        return ExamPaperAnalysisResponse.model_validate_json(response.text)

    # ------------------------------------------------------------------
    # Exam-to-paper matching
    # ------------------------------------------------------------------

    def match_exam_to_paper(
        self,
        system_prompt: str,
        content_blocks: list[dict[str, Any]],
    ) -> ExamMatchingResponse:
        """Match a student exam to the best exam paper template."""
        logger.info("Matching exam to paper with provider %s, model %s", self.provider, self.model)

        if self.provider == "anthropic":
            return self._match_exam_to_paper_anthropic(system_prompt, content_blocks)
        elif self.provider == "openai":
            return self._match_exam_to_paper_openai(system_prompt, content_blocks)
        elif self.provider == "google":
            return self._match_exam_to_paper_google(system_prompt, content_blocks)
        else:
            raise ValueError(f"Unsupported AI provider: {self.provider}")

    def _match_exam_to_paper_anthropic(
        self,
        system_prompt: str,
        content_blocks: list[dict[str, Any]],
    ) -> ExamMatchingResponse:
        tool_def = _pydantic_to_tool(
            "exam_matching_response",
            "Submit the matching result identifying which exam paper template matches the student exam.",
            ExamMatchingResponse,
        )

        response = self.anthropic_client.messages.create(
            model=self.model,
            max_tokens=AI_MAX_TOKENS,
            system=system_prompt,
            messages=[{"role": "user", "content": content_blocks}],
            tools=[tool_def],
            tool_choice={"type": "tool", "name": "exam_matching_response"},
        )

        for block in response.content:
            if block.type == "tool_use" and block.name == "exam_matching_response":
                return ExamMatchingResponse.model_validate(block.input)

        raise ValueError("AI response did not contain expected exam_matching_response tool use")

    def _match_exam_to_paper_openai(
        self,
        system_prompt: str,
        content_blocks: list[dict[str, Any]],
    ) -> ExamMatchingResponse:
        openai_content = self._convert_content_to_openai(content_blocks)
        schema = _make_schema_strict(ExamMatchingResponse.model_json_schema())

        response = self.openai_client.chat.completions.create(
            model=self.model,
            max_completion_tokens=AI_MAX_TOKENS,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": openai_content},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "exam_matching_response",
                    "strict": True,
                    "schema": schema,
                },
            },
        )

        content = response.choices[0].message.content
        if not content:
            raise ValueError("OpenAI response did not contain content")
        return ExamMatchingResponse.model_validate_json(content)

    def _match_exam_to_paper_google(
        self,
        system_prompt: str,
        content_blocks: list[dict[str, Any]],
    ) -> ExamMatchingResponse:
        google_parts = self._convert_content_to_google(content_blocks)

        model = self._genai.GenerativeModel(
            model_name=self.model,
            system_instruction=system_prompt,
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": ExamMatchingResponse.model_json_schema(),
            },
        )

        response = model.generate_content(google_parts)
        if not response.text:
            raise ValueError("Google AI response did not contain content")
        return ExamMatchingResponse.model_validate_json(response.text)

    # ------------------------------------------------------------------
    # Content conversion helpers
    # ------------------------------------------------------------------

    def _convert_content_to_openai(self, content_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert Anthropic-style content blocks to OpenAI format."""
        openai_content = []
        for block in content_blocks:
            if block["type"] == "text":
                openai_content.append({"type": "text", "text": block["text"]})
            elif block["type"] == "image":
                # OpenAI expects base64 images in image_url format
                source = block["source"]
                if source["type"] == "base64":
                    media_type = source.get("media_type", "image/png")
                    openai_content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{source['data']}"
                        }
                    })
        return openai_content

    def _convert_content_to_google(self, content_blocks: list[dict[str, Any]]) -> list[Any]:
        """Convert Anthropic-style content blocks to Google Gemini format."""
        google_parts = []
        for block in content_blocks:
            if block["type"] == "text":
                google_parts.append(block["text"])
            elif block["type"] == "image":
                # Google expects PIL Image or inline data
                source = block["source"]
                if source["type"] == "base64":
                    image_data = base64.b64decode(source["data"])
                    media_type = source.get("media_type", "image/png")
                    google_parts.append({
                        "mime_type": media_type,
                        "data": image_data
                    })
        return google_parts
