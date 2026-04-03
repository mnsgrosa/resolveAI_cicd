from pydantic import BaseModel


class DiagnoseRequest(BaseModel):
    repository: str
    code: str
    issue_description: str
    file_path: str  # used to infer language (e.g. "src/foo.py" → python)


class PatternViolation(BaseModel):
    pattern_name: str
    description: str
    severity: str


class DiagnoseResponse(BaseModel):
    original_code: str
    fixed_code: str
    diagnosis: str
    pattern_violations: list[PatternViolation]
    suggestions: list[str]
    summary: str
