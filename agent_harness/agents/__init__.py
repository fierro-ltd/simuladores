"""Brigada agents."""

from agent_harness.agents.base import AgentConfig, AGENT_MODELS, BaseAgent
from agent_harness.agents.santos import SANTOS_SYSTEM_IDENTITY, SantosPlanner, parse_plan_json
from agent_harness.agents.lamponne import LAMPONNE_SYSTEM_IDENTITY, LAMPONNE_TOOLS, LamponneExecutor
from agent_harness.agents.medina import MEDINA_SYSTEM_IDENTITY, MEDINA_TOOLS, MedinaInvestigator
from agent_harness.agents.qa_reviewer import SANTOS_QA_IDENTITY, QACheck, QAReport, SantosQAReviewer
from agent_harness.agents.ravenna import RAVENNA_SYSTEM_IDENTITY, RAVENNA_TOOLS, RavennaSynthesizer

__all__ = [
    "AgentConfig",
    "AGENT_MODELS",
    "BaseAgent",
    "LAMPONNE_SYSTEM_IDENTITY",
    "LAMPONNE_TOOLS",
    "LamponneExecutor",
    "MEDINA_SYSTEM_IDENTITY",
    "MEDINA_TOOLS",
    "MedinaInvestigator",
    "QACheck",
    "QAReport",
    "RAVENNA_SYSTEM_IDENTITY",
    "RAVENNA_TOOLS",
    "RavennaSynthesizer",
    "SANTOS_QA_IDENTITY",
    "SANTOS_SYSTEM_IDENTITY",
    "SantosPlanner",
    "SantosQAReviewer",
    "parse_plan_json",
]
