"""Role specification models — behavioral rules for each agent."""

from __future__ import annotations

from pydantic import BaseModel, model_validator


class RoleSpec(BaseModel):
    """Detailed role specification loaded from roles/*.yml."""
    name: str
    system_prompt: str
    output_format: str | None = None
    verdict_field: str | None = None
    approve_value: str | None = None
    reject_value: str | None = None

    @model_validator(mode="after")
    def validate_verdict_config(self):
        verdict_fields = [self.verdict_field, self.approve_value, self.reject_value]
        if any(verdict_fields) and not all(verdict_fields):
            raise ValueError(
                "verdict_field, approve_value, and reject_value must all be set or all be unset"
            )
        return self
