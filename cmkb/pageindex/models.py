"""
Pydantic models for PageIndex data structures.
Enforces type safety, reduces token waste, and eliminates parsing errors.
"""
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, validator
import json


# ==================== TOC Models ====================

class TOCItem(BaseModel):
    """Represents a single table of contents entry."""
    structure: Optional[str] = Field(None, description="Hierarchical structure (e.g., '1.2.3')")
    title: str = Field(..., description="Section title", max_length=500)
    page: Optional[int] = Field(None, ge=1, le=10000, description="Page number")
    
    class Config:
        json_schema_extra = {
            "example": {"structure": "1.2", "title": "Background", "page": 45}
        }


class TableOfContents(BaseModel):
    """Complete table of contents."""
    table_of_contents: List[TOCItem] = Field(..., description="List of TOC items")
    
    class Config:
        json_schema_extra = {
            "example": {
                "table_of_contents": [
                    {"structure": "1", "title": "Introduction", "page": 1},
                    {"structure": "1.1", "title": "Background", "page": 3}
                ]
            }
        }


# ==================== Node Models ====================

class PageNode(BaseModel):
    """Represents a node in the document tree."""
    node_id: str = Field(..., description="Unique node identifier", max_length=20)
    title: str = Field(..., description="Node title", max_length=300)
    page_ids: Optional[List[int]] = Field(default_factory=list, description="List of page numbers")
    text: Optional[str] = Field(None, description="Extracted text from node")
    summary: Optional[str] = Field(None, description="Auto-generated summary", max_length=500)
    children: Optional[List[str]] = Field(default_factory=list, description="Child node IDs")
    
    class Config:
        json_schema_extra = {
            "example": {
                "node_id": "0001",
                "title": "Introduction",
                "page_ids": [1, 2, 3],
                "summary": "Covers background and motivation",
                "children": ["0001_1", "0001_2"]
            }
        }


# ==================== Search & Answer Models ====================

class SearchResult(BaseModel):
    """Result from searching the document tree."""
    found_nodes: List[str] = Field(default_factory=list, description="List of matching node IDs")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Search confidence score")
    reasoning: Optional[str] = Field(None, description="Why these nodes match")
    
    class Config:
        json_schema_extra = {
            "example": {
                "found_nodes": ["0001_1", "0001_2"],
                "confidence": 0.92,
                "reasoning": "Both nodes contain relevant information"
            }
        }


class Answer(BaseModel):
    """Generated answer from document search."""
    answer: str = Field(..., description="Concise answer", max_length=2000)
    sources: Optional[List[str]] = Field(default_factory=list, description="Source node IDs")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Answer confidence")
    
    class Config:
        json_schema_extra = {
            "example": {
                "answer": "The background is discussed in section 1.1",
                "sources": ["0001_1"],
                "confidence": 0.95
            }
        }


# ==================== Validation Models ====================

class TitleValidation(BaseModel):
    """Validation response for title appearance checks."""
    answer: Literal["yes", "no"] = Field(..., description="Does title appear in text?")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    page_number: Optional[int] = Field(None)
    
    class Config:
        json_schema_extra = {
            "example": {"answer": "yes", "confidence": 0.95, "page_number": 5}
        }


class StartValidator(BaseModel):
    """Checks if a section starts at a specified location."""
    start_begin: Literal["yes", "no"] = Field(..., description="Does section start here?")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    
    class Config:
        json_schema_extra = {
            "example": {"start_begin": "yes", "confidence": 0.98}
        }


# ==================== Configuration Models ====================

class ModelConfig(BaseModel):
    """Model configuration."""
    model_name: str = Field(..., description="Model identifier")
    max_tokens: int = Field(4096, ge=512, le=32768, description="Max output tokens")
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    top_p: float = Field(0.95, ge=0.0, le=1.0)
    
    class Config:
        json_schema_extra = {
            "example": {
                "model_name": "mistral24b-16k",
                "max_tokens": 16384,
                "temperature": 0.7,
                "top_p": 0.95
            }
        }


# ==================== Helper Functions ====================

def get_toc_schema_json() -> Dict[str, Any]:
    """
    Get compact JSON schema for TOC.
    Used in prompts to inform model of expected structure.
    """
    return {
        "table_of_contents": [
            {"structure": "str|null", "title": "str", "page": "int|null"}
        ]
    }


def get_search_result_schema_json() -> Dict[str, Any]:
    """Get compact schema for search results."""
    return {
        "found_nodes": ["str"],
        "confidence": "float (0.0-1.0)",
        "reasoning": "str"
    }


def get_answer_schema_json() -> Dict[str, Any]:
    """Get compact schema for answers."""
    return {
        "answer": "str",
        "sources": ["str"],
        "confidence": "float (0.0-1.0)"
    }


def format_schema_for_prompt(model_class: type) -> str:
    """
    Format a Pydantic model as a compact prompt instruction.
    
    Example output:
        "Return valid JSON: {\"structure\": \"str|null\", \"title\": \"str\", \"page\": \"int|null\"}"
    """
    schema = model_class.model_json_schema()
    
    # Build compact version
    if model_class == TOCItem:
        return '{{"structure": "str|null", "title": "str", "page": "int|null"}}'
    elif model_class == SearchResult:
        return '{{"found_nodes": ["str"], "confidence": "float", "reasoning": "str"}}'
    elif model_class == Answer:
        return '{{"answer": "str", "sources": ["str"], "confidence": "float"}}'
    
    return str(schema)


# ==================== Validation Utilities ====================

def validate_toc_items(items: List[Dict[str, Any]]) -> List[TOCItem]:
    """
    Parse and validate list of TOC items.
    Returns validated TOCItem objects, skips invalid ones.
    """
    valid_items = []
    for item in items:
        try:
            valid_items.append(TOCItem(**item))
        except Exception as e:
            # Log and skip invalid items
            pass
    return valid_items


def validate_and_parse_json(content: str, model_class: type) -> Optional[Any]:
    """
    Parse JSON string and validate against Pydantic model.
    
    Returns:
        Validated model instance or None if invalid
    """
    try:
        data = json.loads(content)
        return model_class(**data)
    except Exception as e:
        return None
