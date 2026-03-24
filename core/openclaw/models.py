"""数据模型：任务、步骤、结果"""
from __future__ import annotations
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    REWORK = "rework"
    COMPLETED = "completed"
    FAILED = "failed"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    SKIPPED = "skipped"


@dataclass
class Step:
    step_id: int
    description: str
    assigned_to: str  # "researcher" | "executor"
    requires_remote: bool = False
    depends_on: list[int] = field(default_factory=list)
    expected_output: str = ""
    status: StepStatus = StepStatus.PENDING
    result: dict[str, Any] | None = None
    started_at: float | None = None
    finished_at: float | None = None

    @property
    def duration(self) -> float | None:
        if self.started_at and self.finished_at:
            return self.finished_at - self.started_at
        return None


@dataclass
class Plan:
    task_summary: str
    task_type: str  # "research" | "execute" | "hybrid"
    steps: list[Step] = field(default_factory=list)
    review_needed: bool = True
    estimated_complexity: str = "medium"
    raw_response: str = ""


@dataclass
class ReviewResult:
    quality_score: int = 0
    needs_rework: bool = False
    rework_instructions: str | None = None
    final_output: str = ""
    review_items: list[dict] = field(default_factory=list)
    raw_response: str = ""


@dataclass
class Task:
    """顶层任务对象，贯穿整个生命周期"""
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    user_input: str = ""
    source: str = "telegram"  # "telegram" | "cli" | "api"
    status: TaskStatus = TaskStatus.PENDING
    plan: Plan | None = None
    step_results: dict[int, dict[str, Any]] = field(default_factory=dict)
    review: ReviewResult | None = None
    rework_count: int = 0
    max_rework: int = 2
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    error: str | None = None

    @property
    def duration(self) -> float | None:
        if self.finished_at:
            return self.finished_at - self.created_at
        return None

    def to_summary(self) -> str:
        lines = [
            f"任务 [{self.task_id}] {self.status.value}",
            f"输入: {self.user_input[:80]}...",
        ]
        if self.plan:
            lines.append(f"计划: {self.plan.task_summary}")
            lines.append(f"步骤: {len(self.plan.steps)} 步")
        if self.review:
            lines.append(f"评分: {self.review.quality_score}/10")
        if self.duration:
            lines.append(f"耗时: {self.duration:.1f}s")
        if self.error:
            lines.append(f"错误: {self.error}")
        return "\n".join(lines)
