"""
Approval Agent Module

Human-in-the-loop approval workflow using LangGraph interrupts and Slack integration.
"""

from backend.modules.approval.state import ApprovalState
from backend.modules.approval.graph import approval_subgraph, build_approval_subgraph

__all__ = [
    "ApprovalState",
    "approval_subgraph",
    "build_approval_subgraph",
]
