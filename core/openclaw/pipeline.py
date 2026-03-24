"""任务管线：planner → researcher|executor → reviewer"""
from __future__ import annotations
import json
import logging
import time
from typing import Any

from .config import Config, config
from .models import Task, TaskStatus, Plan, Step, StepStatus, ReviewResult
from .llm import llm

logger = logging.getLogger("openclaw.pipeline")


class Pipeline:
    """
    核心任务管线，编排四个角色协作完成任务。

    流程:
      1. planner 分析任务、拆解步骤
      2. 按步骤分配给 researcher 或 executor
      3. reviewer 审查结果
      4. 如需返工，回到步骤 2（最多 max_rework 次）
    """

    def __init__(self, cfg: Config | None = None):
        self.cfg = cfg or config

    async def run(self, task: Task) -> Task:
        """执行完整管线"""
        logger.info(f"开始任务 [{task.task_id}]: {task.user_input[:60]}...")

        try:
            # Phase 1: Planning
            task.status = TaskStatus.PLANNING
            task.plan = await self._plan(task)
            logger.info(f"规划完成: {task.plan.task_summary}")

            # Phase 2: Execute steps
            task.status = TaskStatus.EXECUTING
            await self._execute_steps(task)

            # Phase 3: Review
            if task.plan.review_needed:
                task.status = TaskStatus.REVIEWING
                task.review = await self._review(task)

                # Rework loop
                while (
                    task.review.needs_rework
                    and task.rework_count < task.max_rework
                ):
                    task.rework_count += 1
                    task.status = TaskStatus.REWORK
                    logger.info(f"返工第 {task.rework_count} 轮")
                    await self._rework(task)
                    task.review = await self._review(task)
            else:
                # 简单任务，直接汇总
                task.review = ReviewResult(
                    quality_score=8,
                    final_output=self._quick_summarize(task),
                )

            task.status = TaskStatus.COMPLETED
            task.finished_at = time.time()
            logger.info(
                f"任务完成 [{task.task_id}] "
                f"评分={task.review.quality_score} "
                f"耗时={task.duration:.1f}s"
            )

        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.finished_at = time.time()
            logger.error(f"任务失败 [{task.task_id}]: {e}", exc_info=True)

        return task

    # ---- Phase 1: Planning ----

    async def _plan(self, task: Task) -> Plan:
        role_cfg = self.cfg.roles["planner"]
        model_cfg = self.cfg.get_model(role_cfg.model)

        # 构建上下文信息
        context_parts = [f"用户任务: {task.user_input}"]

        # 告知 planner 可用的远程 worker
        active_workers = self.cfg.get_active_workers()
        if active_workers:
            caps = {w.name: w.capabilities for w in active_workers}
            context_parts.append(f"可用远程 worker: {json.dumps(caps, ensure_ascii=False)}")
        else:
            context_parts.append("注意: 当前没有可用的远程 worker，所有任务必须在本地完成。")

        user_msg = "\n".join(context_parts)

        result = await llm.chat_json(
            model_config=model_cfg,
            system_prompt=role_cfg.prompt,
            user_message=user_msg,
            temperature=0.3,
        )

        # 解析计划
        steps = []
        for s in result.get("steps", []):
            steps.append(Step(
                step_id=s.get("step_id", len(steps) + 1),
                description=s.get("description", ""),
                assigned_to=s.get("assigned_to", "executor"),
                requires_remote=s.get("requires_remote", False),
                depends_on=s.get("depends_on", []),
                expected_output=s.get("expected_output", ""),
            ))

        return Plan(
            task_summary=result.get("task_summary", task.user_input[:50]),
            task_type=result.get("task_type", "execute"),
            steps=steps,
            review_needed=result.get("review_needed", True),
            estimated_complexity=result.get("estimated_complexity", "medium"),
            raw_response=json.dumps(result, ensure_ascii=False),
        )

    # ---- Phase 2: Execution ----

    async def _execute_steps(self, task: Task):
        if not task.plan:
            return

        for step in task.plan.steps:
            # 检查依赖是否完成
            for dep_id in step.depends_on:
                dep_result = task.step_results.get(dep_id, {})
                if dep_result.get("status") == "failure":
                    step.status = StepStatus.SKIPPED
                    logger.warning(f"跳过步骤 {step.step_id}（依赖 {dep_id} 失败）")
                    continue

            step.started_at = time.time()
            step.status = StepStatus.RUNNING

            try:
                result = await self._execute_single_step(task, step)
                step.result = result
                step.status = StepStatus(result.get("status", "success"))
                task.step_results[step.step_id] = result
            except Exception as e:
                step.status = StepStatus.FAILURE
                task.step_results[step.step_id] = {
                    "status": "failure",
                    "error": str(e),
                }
                logger.error(f"步骤 {step.step_id} 执行失败: {e}")
            finally:
                step.finished_at = time.time()

    async def _execute_single_step(self, task: Task, step: Step) -> dict[str, Any]:
        role_name = step.assigned_to  # "researcher" or "executor"
        role_cfg = self.cfg.roles.get(role_name)

        if not role_cfg or not role_cfg.enabled:
            return {"status": "failure", "error": f"角色 {role_name} 未启用"}

        model_cfg = self.cfg.get_model(role_cfg.model)

        # 构建上下文
        context = {
            "task_summary": task.plan.task_summary if task.plan else "",
            "step": {
                "step_id": step.step_id,
                "description": step.description,
                "expected_output": step.expected_output,
                "requires_remote": step.requires_remote,
            },
            "previous_results": {
                k: v for k, v in task.step_results.items()
                if k < step.step_id
            },
        }

        # 如果需要远程但没有可用 worker
        if step.requires_remote and not self.cfg.get_active_workers():
            return {
                "status": "failure",
                "error": "此步骤需要远程 worker，但当前没有可用的远程 worker。",
                "notes": "请在 remote-workers.json 中启用 AWS worker。"
            }

        result = await llm.chat_json(
            model_config=model_cfg,
            system_prompt=role_cfg.prompt,
            user_message=json.dumps(context, ensure_ascii=False, indent=2),
            temperature=0.5,
        )

        result.setdefault("step_id", step.step_id)
        result.setdefault("status", "success")
        return result

    # ---- Phase 3: Review ----

    async def _review(self, task: Task) -> ReviewResult:
        role_cfg = self.cfg.roles["reviewer"]
        model_cfg = self.cfg.get_model(role_cfg.model)

        context = {
            "task_summary": task.plan.task_summary if task.plan else "",
            "original_input": task.user_input,
            "steps": [
                {
                    "step_id": s.step_id,
                    "description": s.description,
                    "assigned_to": s.assigned_to,
                    "status": s.status.value,
                    "result": task.step_results.get(s.step_id, {}),
                }
                for s in (task.plan.steps if task.plan else [])
            ],
            "rework_count": task.rework_count,
        }

        result = await llm.chat_json(
            model_config=model_cfg,
            system_prompt=role_cfg.prompt,
            user_message=json.dumps(context, ensure_ascii=False, indent=2),
            temperature=0.3,
        )

        return ReviewResult(
            quality_score=result.get("quality_score", 5),
            needs_rework=result.get("needs_rework", False),
            rework_instructions=result.get("rework_instructions"),
            final_output=result.get("final_output", ""),
            review_items=result.get("review_items", []),
            raw_response=json.dumps(result, ensure_ascii=False),
        )

    # ---- Rework ----

    async def _rework(self, task: Task):
        """根据 reviewer 反馈重新执行需要返工的步骤"""
        if not task.review or not task.plan:
            return

        for item in task.review.review_items:
            if item.get("status") == "fail":
                step_id = item.get("step_id")
                # 找到对应步骤重新执行
                for step in task.plan.steps:
                    if step.step_id == step_id:
                        step.status = StepStatus.PENDING
                        logger.info(f"返工步骤 {step_id}: {item.get('suggestion', '')}")
                        break

        await self._execute_steps(task)

    # ---- Utils ----

    @staticmethod
    def _quick_summarize(task: Task) -> str:
        parts = []
        for sid, result in sorted(task.step_results.items()):
            output = result.get("output", result.get("summary", ""))
            if output:
                parts.append(str(output))
        return "\n".join(parts) if parts else "任务已完成，但没有产出具体输出。"
