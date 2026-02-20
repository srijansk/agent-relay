"""Orchestrator — intelligent layer that holds intent, evaluates agent outputs, and course-corrects.

The orchestrator wraps the mechanical state machine with an LLM-powered evaluation layer.
Before each agent step, it enriches the prompt with intent and prior context.
After each step, it evaluates whether the output aligns with the vision.

When disabled (the default), the workflow runs mechanically via the state machine.
When enabled, the orchestrator adds:
  1. Intent injection into every agent prompt
  2. Post-step output evaluation against the intent
  3. Course correction (re-run with feedback or adjust next step's context)
  4. A persistent context log that accumulates across the workflow
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import yaml


@dataclass
class OrchestratorNote:
    """A single entry in the orchestrator's context log."""
    stage: str
    role: str
    action: Literal["proceeded", "corrected", "re_run", "overridden"]
    summary: str
    concerns: list[str] = field(default_factory=list)
    enrichment_given: str = ""
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(tz=timezone.utc).isoformat()


@dataclass
class PreStepResult:
    """Decision from the orchestrator before invoking an agent."""
    proceed: bool = True
    prompt_enrichment: str = ""
    override_stage: str | None = None
    reasoning: str = ""


@dataclass
class PostStepResult:
    """Decision from the orchestrator after an agent completes."""
    aligned: bool = True
    should_rerun: bool = False
    rerun_feedback: str = ""
    concerns: list[str] = field(default_factory=list)
    summary: str = ""
    override_verdict: str | None = None
    reasoning: str = ""


class Orchestrator:
    """Intelligent workflow orchestrator that holds intent and evaluates agent outputs.

    The orchestrator makes two LLM calls per agent step:
    1. Pre-step: Should we proceed? Any prompt adjustments?
    2. Post-step: Does the output align with the intent?

    These calls are cheap (short context, not full artifacts) and add
    ~2-5 seconds per step in exchange for intent-aware orchestration.
    """

    def __init__(
        self,
        intent: str,
        provider: str = "openai",
        model: str = "gpt-4o",
        api_key: str | None = None,
        log_path: Path | None = None,
    ):
        self.intent = intent
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.log_path = log_path
        self.notes: list[OrchestratorNote] = []

        if log_path and log_path.exists():
            self._load_log()

    async def pre_step(
        self,
        stage: str,
        role_name: str,
        role_description: str,
        artifact_summaries: dict[str, str],
    ) -> PreStepResult:
        """Evaluate before invoking an agent. Returns prompt enrichments.

        Args:
            stage: Current stage name
            role_name: The agent role about to be invoked
            role_description: What this role does
            artifact_summaries: {filename: first 500 chars} of relevant artifacts
        """
        context = self._build_context_summary()

        system = (
            "You are a workflow orchestrator. You hold the product intent and evaluate "
            "whether each step in a multi-agent pipeline stays aligned with the vision. "
            "Be concise. Respond in the exact format requested."
        )

        prompt = f"""## Intent
{self.intent}

## Current State
- Stage: {stage}
- Next agent: {role_name} ({role_description})
- Steps completed: {len(self.notes)}

## Prior Context
{context if context else "No prior steps yet."}

## Artifact Summaries
{self._format_artifact_summaries(artifact_summaries)}

## Your Task
Based on the intent and prior context, provide:
1. PROCEED: yes or no (should this agent run?)
2. ENRICHMENT: Additional context or instructions to add to this agent's prompt to keep it aligned with the intent. This is injected into the agent's prompt as "Orchestrator Notes." Keep it to 2-4 sentences max. If no enrichment needed, write "none".
3. REASONING: One sentence explaining your decision.

Respond in this exact format:
PROCEED: yes
ENRICHMENT: <text or "none">
REASONING: <one sentence>"""

        response = await self._call_llm(system, prompt)
        return self._parse_pre_step(response)

    async def post_step(
        self,
        stage: str,
        role_name: str,
        output_summary: str,
    ) -> PostStepResult:
        """Evaluate after an agent completes. Returns alignment assessment.

        Args:
            stage: Current stage name
            role_name: The agent that just ran
            output_summary: First 2000 chars of the agent's output
        """
        context = self._build_context_summary()

        system = (
            "You are a workflow orchestrator evaluating an agent's output. "
            "Be concise and decisive. Respond in the exact format requested."
        )

        prompt = f"""## Intent
{self.intent}

## Agent That Just Ran
- Stage: {stage}
- Role: {role_name}

## Prior Context
{context if context else "This was the first step."}

## Agent Output (summary)
{output_summary[:2000]}

## Your Task
Evaluate whether this output aligns with the intent and is good enough to proceed.
1. ALIGNED: yes or no
2. RERUN: yes or no (should we re-run this agent with corrections?)
3. CONCERNS: Any concerns to flag for the next agent (comma-separated, or "none")
4. SUMMARY: One-sentence summary of what this agent produced
5. REASONING: One sentence explaining your assessment

Respond in this exact format:
ALIGNED: yes
RERUN: no
CONCERNS: none
SUMMARY: <one sentence>
REASONING: <one sentence>"""

        response = await self._call_llm(system, prompt)
        result = self._parse_post_step(response)

        action = "proceeded" if result.aligned else ("re_run" if result.should_rerun else "corrected")
        self.notes.append(OrchestratorNote(
            stage=stage,
            role=role_name,
            action=action,
            summary=result.summary,
            concerns=result.concerns,
        ))
        self._save_log()

        return result

    def get_enrichment_for_prompt(self) -> str:
        """Build the orchestrator context block to inject into agent prompts.

        This includes the intent and a summary of prior steps with any concerns.
        """
        parts = [
            "## Orchestrator Context",
            "",
            "### Intent",
            self.intent,
            "",
        ]

        if self.notes:
            parts.append("### Prior Steps")
            for note in self.notes[-5:]:  # Last 5 steps to keep context manageable
                concern_str = f" | Concerns: {', '.join(note.concerns)}" if note.concerns else ""
                parts.append(f"- [{note.role}] {note.summary}{concern_str}")
            parts.append("")

        return "\n".join(parts)

    def _build_context_summary(self) -> str:
        """Build a concise summary of prior steps for the orchestrator's own LLM calls."""
        if not self.notes:
            return ""
        lines = []
        for note in self.notes[-5:]:
            concern_str = f" (concerns: {', '.join(note.concerns)})" if note.concerns else ""
            lines.append(f"- {note.role} [{note.action}]: {note.summary}{concern_str}")
        return "\n".join(lines)

    def _format_artifact_summaries(self, summaries: dict[str, str]) -> str:
        if not summaries:
            return "No artifacts yet."
        lines = []
        for name, content in summaries.items():
            preview = content[:500].replace("\n", " ")
            lines.append(f"- {name}: {preview}...")
        return "\n".join(lines)

    async def _call_llm(self, system: str, prompt: str) -> str:
        """Make an LLM call to the configured provider."""
        if self.provider == "openai":
            return await self._call_openai(system, prompt)
        elif self.provider == "anthropic":
            return await self._call_anthropic(system, prompt)
        else:
            raise ValueError(f"Orchestrator provider must be 'openai' or 'anthropic', got '{self.provider}'")

    async def _call_openai(self, system: str, prompt: str) -> str:
        try:
            from openai import AsyncOpenAI
        except ImportError:
            raise ImportError(
                "Orchestrator requires OpenAI. Install with: pip install agent-relay[openai]"
            )

        client = AsyncOpenAI(api_key=self.api_key)
        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=512,
        )
        return response.choices[0].message.content or ""

    async def _call_anthropic(self, system: str, prompt: str) -> str:
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            raise ImportError(
                "Orchestrator requires Anthropic. Install with: pip install agent-relay[anthropic]"
            )

        client = AsyncAnthropic(api_key=self.api_key)
        response = await client.messages.create(
            model=self.model,
            system=system,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=512,
        )
        parts = [block.text for block in response.content if hasattr(block, "text")]
        return "\n".join(parts)

    def _parse_pre_step(self, response: str) -> PreStepResult:
        """Parse the structured response from pre-step evaluation."""
        result = PreStepResult()
        for line in response.strip().splitlines():
            line = line.strip()
            if line.upper().startswith("PROCEED:"):
                result.proceed = "yes" in line.lower()
            elif line.upper().startswith("ENRICHMENT:"):
                val = line.split(":", 1)[1].strip()
                result.prompt_enrichment = "" if val.lower() == "none" else val
            elif line.upper().startswith("REASONING:"):
                result.reasoning = line.split(":", 1)[1].strip()
        return result

    def _parse_post_step(self, response: str) -> PostStepResult:
        """Parse the structured response from post-step evaluation."""
        result = PostStepResult()
        for line in response.strip().splitlines():
            line = line.strip()
            if line.upper().startswith("ALIGNED:"):
                result.aligned = "yes" in line.lower()
            elif line.upper().startswith("RERUN:"):
                result.should_rerun = "yes" in line.lower()
            elif line.upper().startswith("CONCERNS:"):
                val = line.split(":", 1)[1].strip()
                if val.lower() != "none":
                    result.concerns = [c.strip() for c in val.split(",") if c.strip()]
            elif line.upper().startswith("SUMMARY:"):
                result.summary = line.split(":", 1)[1].strip()
            elif line.upper().startswith("REASONING:"):
                result.reasoning = line.split(":", 1)[1].strip()
        return result

    def _save_log(self) -> None:
        """Persist the orchestrator notes to disk."""
        if not self.log_path:
            return
        data = [
            {
                "stage": n.stage,
                "role": n.role,
                "action": n.action,
                "summary": n.summary,
                "concerns": n.concerns,
                "enrichment_given": n.enrichment_given,
                "timestamp": n.timestamp,
            }
            for n in self.notes
        ]
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))

    def _load_log(self) -> None:
        """Load orchestrator notes from disk."""
        if not self.log_path or not self.log_path.exists():
            return
        raw = yaml.safe_load(self.log_path.read_text())
        if not isinstance(raw, list):
            return
        self.notes = [OrchestratorNote(**entry) for entry in raw]
