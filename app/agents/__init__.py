"""Agentic framework — each agent is autonomous, has a role, tools, and produces a verdict."""
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum


class AgentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class AgentResult:
    agent: str
    status: AgentStatus
    verdict: str = ""
    confidence: int = 0
    summary: str = ""
    details: dict = field(default_factory=dict)
    duration_ms: int = 0
    issues: list = field(default_factory=list)
    suggestions: list = field(default_factory=list)


class BaseAgent:
    """All agents inherit from this. Each agent has a name, role description,
    and a run() method that returns an AgentResult."""

    name: str = "base"
    role: str = "Base agent"

    def run(self, context: dict) -> AgentResult:
        raise NotImplementedError

    def safe_run(self, context: dict) -> AgentResult:
        start = time.time()
        try:
            result = self.run(context)
            result.duration_ms = int((time.time() - start) * 1000)
            return result
        except Exception as e:
            return AgentResult(
                agent=self.name,
                status=AgentStatus.FAILED,
                verdict="ERROR",
                summary=f"Agent failed: {str(e)}",
                details={"traceback": traceback.format_exc()},
                duration_ms=int((time.time() - start) * 1000),
            )
