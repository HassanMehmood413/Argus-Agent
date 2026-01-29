# 🚨 Intelligent DevOps Incident Response Agent

An AI-powered multi-agent system built with LangGraph that monitors production infrastructure, detects anomalies, investigates issues, and coordinates incident response with human-in-the-loop approval.

![Architecture Overview](docs/images/architecture-overview.png)

---

## 📋 Table of Contents

1. [Project Overview](#-project-overview)
2. [Architecture](#-architecture)
3. [Tech Stack](#-tech-stack)
4. [Prerequisites](#-prerequisites)
5. [Development Roadmap](#-development-roadmap)
   - [Phase 1: Foundation & Core Setup](#phase-1-foundation--core-setup-week-1)
   - [Phase 2: Agent Development](#phase-2-agent-development-week-2)
   - [Phase 3: Human-in-the-Loop & Persistence](#phase-3-human-in-the-loop--persistence-week-3)
   - [Phase 4: Monitoring & Alerting Integration](#phase-4-monitoring--alerting-integration-week-4)
   - [Phase 5: Communication & Notifications](#phase-5-communication--notifications-week-5)
   - [Phase 6: Configuration UI](#phase-6-configuration-ui-week-6)
   - [Phase 7: Production Hardening](#phase-7-production-hardening-week-7)
   - [Phase 8: Deployment & DevOps](#phase-8-deployment--devops-week-8)
6. [Project Structure](#-project-structure)
7. [Configuration Guide](#-configuration-guide)
8. [API Reference](#-api-reference)
9. [Contributing](#-contributing)
10. [License](#-license)

---

## 🎯 Project Overview

### What This Project Does

This system acts as an intelligent DevOps assistant that:

1. **Monitors** your infrastructure 24/7 (Prometheus, CloudWatch, Kubernetes)
2. **Detects** anomalies and issues automatically
3. **Analyzes** root causes using AI + historical incident data
4. **Proposes** remediation actions based on runbooks and past resolutions
5. **Requests approval** from humans before taking critical actions
6. **Executes** approved actions (restart pods, rollback deployments, scale resources)
7. **Learns** from each incident to improve future responses

### Why Build This?

- **Real-world application**: Companies like Uber, LinkedIn, and Klarna use similar systems
- **Production-grade learning**: Practice Docker, Kubernetes, observability, and AI agents
- **Portfolio piece**: Demonstrates enterprise-level engineering skills
- **Solves real problems**: Reduces MTTR (Mean Time To Resolution) from hours to minutes

---

## 🏗 Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL SYSTEMS                                │
├─────────────────────────────────────────────────────────────────────────┤
│  Prometheus  │  Grafana  │  Kubernetes  │  Slack  │  PagerDuty  │  Jira │
└──────┬───────┴─────┬─────┴──────┬───────┴────┬────┴──────┬──────┴───┬───┘
       │             │            │            │           │          │
       └─────────────┴────────────┼────────────┴───────────┴──────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │     CONFIGURATION API     │
                    │   (FastAPI + PostgreSQL)  │
                    └─────────────┬─────────────┘
                                  │
┌─────────────────────────────────▼─────────────────────────────────────┐
│                        LANGGRAPH AGENT SYSTEM                         │
├───────────────────────────────────────────────────────────────────────┤
│                                                                       │
│   ┌─────────────────────────────────────────────────────────────┐    │
│   │                    SUPERVISOR AGENT                          │    │
│   │              (Orchestrates all other agents)                 │    │
│   └───────────────────────────┬─────────────────────────────────┘    │
│                               │                                       │
│       ┌───────────┬───────────┼───────────┬───────────┐              │
│       ▼           ▼           ▼           ▼           ▼              │
│   ┌───────┐   ┌───────┐   ┌───────┐   ┌───────┐   ┌───────┐         │
│   │Monitor│   │Analyzer│  │Action │   │ Comms │   │Memory │         │
│   │ Agent │   │ Agent │   │ Agent │   │ Agent │   │ Agent │         │
│   └───────┘   └───────┘   └───────┘   └───────┘   └───────┘         │
│                                                                       │
│   ┌─────────────────────────────────────────────────────────────┐    │
│   │                 HUMAN-IN-THE-LOOP NODE                       │    │
│   │         (Pauses for approval on critical actions)            │    │
│   └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
                                  │
                    ┌─────────────▼─────────────┐
                    │      STATE STORAGE        │
                    │  (PostgreSQL + Redis)     │
                    └───────────────────────────┘
```

### Agent Responsibilities

| Agent | Role | Tools |
|-------|------|-------|
| **Supervisor** | Orchestrates workflow, decides next steps | Agent invocation, state management |
| **Monitor** | Gathers real-time infrastructure data | Prometheus, CloudWatch, K8s API, Logs |
| **Analyzer** | Root cause analysis, pattern matching | RAG over incidents, metric correlation |
| **Action** | Executes remediation (with safety checks) | kubectl, AWS CLI, restart scripts |
| **Comms** | Human communication | Slack, PagerDuty, Jira, Email |
| **Memory** | Stores and retrieves learnings | Vector DB, knowledge base |

### Incident Flow

```
Alert Received
      │
      ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Supervisor │────▶│   Monitor   │────▶│  Supervisor │
│  "Get data" │     │ Gather info │     │"Analyze it" │
└─────────────┘     └─────────────┘     └─────────────┘
                                              │
      ┌───────────────────────────────────────┘
      ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Analyzer   │────▶│  Supervisor │────▶│    Comms    │
│  Find cause │     │"Need approval"│   │ Ask in Slack│
└─────────────┘     └─────────────┘     └─────────────┘
                                              │
      ┌───────────────────────────────────────┘
      ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   HUMAN     │────▶│   Action    │────▶│   Monitor   │
│  Approves   │     │  Execute    │     │   Verify    │
└─────────────┘     └─────────────┘     └─────────────┘
                                              │
      ┌───────────────────────────────────────┘
      ▼
┌─────────────┐     ┌─────────────┐
│    Comms    │────▶│    END      │
│ Post summary│     │  Resolved   │
└─────────────┘     └─────────────┘
```

---

## 🛠 Tech Stack

### Core Technologies

| Category | Technology | Purpose |
|----------|------------|---------|
| **AI Framework** | LangGraph 1.0+ | Multi-agent orchestration |
| **LLM** | Claude 3.5 Sonnet | Reasoning and analysis |
| **Backend** | FastAPI | Configuration API |
| **Database** | PostgreSQL | State persistence, checkpointing |
| **Cache** | Redis | Caching, pub/sub |
| **Vector DB** | Pinecone / Qdrant | RAG for past incidents |

### Infrastructure & DevOps

| Category | Technology | Purpose |
|----------|------------|---------|
| **Containerization** | Docker | Local development |
| **Orchestration** | Kubernetes | Production deployment |
| **Monitoring** | Prometheus + Grafana | Metrics and visualization |
| **Logging** | ELK Stack / Loki | Log aggregation |
| **Tracing** | LangSmith | Agent observability |

### Integrations

| Category | Technology | Purpose |
|----------|------------|---------|
| **Communication** | Slack API | Notifications and approvals |
| **Alerting** | PagerDuty | On-call escalation |
| **Ticketing** | Jira API | Incident tickets |
| **Cloud** | AWS SDK | Cloud resource management |

---

## 📚 Prerequisites

Before starting, ensure you have:

### Required Knowledge
- [ ] Python (intermediate - async, type hints, decorators)
- [ ] Docker basics (containers, volumes, networks)
- [ ] REST APIs (FastAPI or Flask)
- [ ] Basic understanding of Kubernetes concepts

### Nice to Have
- [ ] LangChain / LangGraph experience
- [ ] Prometheus / Grafana exposure
- [ ] Slack app development

### Required Accounts & Tools
- [ ] Python 3.11+
- [ ] Docker Desktop
- [ ] kubectl (Kubernetes CLI)
- [ ] Anthropic API key (for Claude)
- [ ] Slack workspace (for testing)
- [ ] GitHub account

### Development Environment
```bash
# Verify installations
python --version    # 3.11+
docker --version    # 24.0+
kubectl version     # 1.28+
```

---

## 🗺 Development Roadmap

---

## Phase 1: Foundation & Core Setup (Week 1)

### 🎯 Goals
- Set up project structure
- Configure development environment
- Create basic LangGraph skeleton
- Implement configuration system

### 📋 Tasks

#### Day 1-2: Project Setup

**1.1 Initialize Project Structure**
```bash
# Create project directory
mkdir devops-incident-agent
cd devops-incident-agent

# Initialize git
git init

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Create directory structure
mkdir -p src/{agents,tools,config,api,models}
mkdir -p tests/{unit,integration}
mkdir -p docker
mkdir -p k8s
mkdir -p docs/images
```

**1.2 Create Requirements Files**

Create `requirements.txt`:
```txt
# Core
langgraph>=0.2.0
langchain>=0.3.0
langchain-anthropic>=0.2.0
langchain-community>=0.3.0

# API
fastapi>=0.109.0
uvicorn>=0.27.0
pydantic>=2.5.0
pydantic-settings>=2.1.0

# Database
asyncpg>=0.29.0
sqlalchemy>=2.0.0
alembic>=1.13.0
redis>=5.0.0

# Vector Store
pinecone-client>=3.0.0

# Monitoring Tools
prometheus-api-client>=0.5.0
kubernetes>=28.0.0

# Communication
slack-sdk>=3.27.0

# Utilities
httpx>=0.26.0
python-dotenv>=1.0.0
structlog>=24.1.0
tenacity>=8.2.0

# Testing
pytest>=7.4.0
pytest-asyncio>=0.23.0
pytest-cov>=4.1.0
```

Create `requirements-dev.txt`:
```txt
-r requirements.txt
black>=24.1.0
ruff>=0.1.0
mypy>=1.8.0
pre-commit>=3.6.0
```

**1.3 Install Dependencies**
```bash
pip install -r requirements-dev.txt
```

**1.4 Create Configuration Files**

Create `.env.example`:
```env
# LLM
ANTHROPIC_API_KEY=your-api-key-here

# Database
POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/incident_agent
REDIS_URL=redis://localhost:6379/0

# Monitoring (to be configured later)
PROMETHEUS_URL=http://localhost:9090
GRAFANA_URL=http://localhost:3000
GRAFANA_API_KEY=

# Slack (to be configured later)
SLACK_BOT_TOKEN=
SLACK_APP_TOKEN=
SLACK_INCIDENTS_CHANNEL=

# Environment
ENVIRONMENT=development
LOG_LEVEL=DEBUG
```

Create `pyproject.toml`:
```toml
[project]
name = "devops-incident-agent"
version = "0.1.0"
description = "AI-powered DevOps incident response agent"
requires-python = ">=3.11"

[tool.black]
line-length = 100
target-version = ['py311']

[tool.ruff]
line-length = 100
select = ["E", "F", "I", "N", "W"]

[tool.mypy]
python_version = "3.11"
strict = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

#### Day 3-4: Configuration System

**1.5 Create Configuration Schema**

Create `src/config/schema.py`:
```python
"""
Configuration schema for the DevOps Incident Agent.
Users configure these settings to connect the agent to their infrastructure.
"""

from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, SecretStr, HttpUrl, Field


class AuthType(str, Enum):
    """Authentication types supported for data sources."""
    NONE = "none"
    BASIC = "basic"
    TOKEN = "token"
    API_KEY = "api_key"


# ============================================================================
# DATA SOURCE CONFIGURATIONS
# ============================================================================

class PrometheusConfig(BaseModel):
    """Prometheus server configuration."""
    url: HttpUrl = Field(..., description="Prometheus server URL")
    auth_type: AuthType = Field(default=AuthType.NONE)
    username: Optional[str] = Field(default=None, description="Basic auth username")
    password: Optional[SecretStr] = Field(default=None, description="Basic auth password")
    token: Optional[SecretStr] = Field(default=None, description="Bearer token")
    
    # Query restrictions
    allowed_metric_patterns: List[str] = Field(
        default=["*"],
        description="Metric patterns agent is allowed to query"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://prometheus.example.com",
                "auth_type": "token",
                "token": "your-token-here"
            }
        }


class GrafanaConfig(BaseModel):
    """Grafana server configuration."""
    url: HttpUrl
    api_key: SecretStr
    
    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://grafana.example.com",
                "api_key": "your-api-key"
            }
        }


class ElasticsearchConfig(BaseModel):
    """Elasticsearch configuration for log searching."""
    url: HttpUrl
    api_key: Optional[SecretStr] = None
    username: Optional[str] = None
    password: Optional[SecretStr] = None
    index_pattern: str = Field(default="logs-*")
    
    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://elasticsearch.example.com:9200",
                "index_pattern": "application-logs-*"
            }
        }


class KubernetesConfig(BaseModel):
    """Kubernetes cluster configuration."""
    # Connection method
    in_cluster: bool = Field(
        default=False,
        description="Set to True if agent runs inside the cluster"
    )
    kubeconfig_path: Optional[str] = Field(
        default=None,
        description="Path to kubeconfig file"
    )
    context: Optional[str] = Field(
        default=None,
        description="Kubernetes context to use"
    )
    
    # Access restrictions
    allowed_namespaces: List[str] = Field(
        default=["default"],
        description="Namespaces agent can access"
    )
    forbidden_namespaces: List[str] = Field(
        default=["kube-system", "kube-public"],
        description="Namespaces agent cannot access"
    )


# ============================================================================
# NOTIFICATION CONFIGURATIONS
# ============================================================================

class SlackConfig(BaseModel):
    """Slack integration configuration."""
    bot_token: SecretStr = Field(..., description="Slack bot OAuth token (xoxb-...)")
    app_token: Optional[SecretStr] = Field(
        default=None,
        description="Slack app token for socket mode (xapp-...)"
    )
    incidents_channel: str = Field(
        default="#incidents",
        description="Channel for incident notifications"
    )
    updates_channel: Optional[str] = Field(
        default=None,
        description="Channel for non-urgent updates"
    )
    
    # Approval settings
    approver_user_ids: List[str] = Field(
        default=[],
        description="Slack user IDs who can approve actions"
    )
    approver_group_ids: List[str] = Field(
        default=[],
        description="Slack user group IDs who can approve"
    )


class PagerDutyConfig(BaseModel):
    """PagerDuty integration configuration."""
    api_key: SecretStr
    service_id: str
    escalation_policy_id: Optional[str] = None


# ============================================================================
# PERMISSION CONFIGURATIONS
# ============================================================================

class ActionPermissions(BaseModel):
    """
    Defines what actions the agent can perform.
    This is critical for safety - controls what the agent can do to your infra.
    """
    
    # Actions that execute without approval
    auto_approved: List[str] = Field(
        default=[
            "query_metrics",
            "search_logs", 
            "get_pod_status",
            "list_deployments",
            "get_service_health"
        ],
        description="Read-only actions that don't need approval"
    )
    
    # Actions that require human approval
    requires_approval: List[str] = Field(
        default=[
            "restart_pod",
            "scale_deployment",
            "rollback_deployment",
            "clear_cache",
            "kill_process"
        ],
        description="Actions that need human approval before execution"
    )
    
    # Actions that are NEVER allowed
    forbidden: List[str] = Field(
        default=[
            "delete_namespace",
            "delete_pvc",
            "delete_deployment",
            "drop_database",
            "terminate_instance"
        ],
        description="Dangerous actions that are never allowed"
    )
    
    # Auto-approve for low severity incidents
    auto_approve_low_severity: bool = Field(
        default=False,
        description="Auto-approve actions for low severity incidents"
    )
    
    # Maximum severity for auto-approval
    auto_approve_max_severity: str = Field(
        default="low",
        description="Maximum severity level for auto-approval (low/medium)"
    )


# ============================================================================
# AGENT BEHAVIOR CONFIGURATION
# ============================================================================

class AgentBehaviorConfig(BaseModel):
    """Configuration for agent behavior and tuning."""
    
    # Monitoring
    check_interval_seconds: int = Field(
        default=60,
        description="How often to check for new alerts"
    )
    alert_cooldown_minutes: int = Field(
        default=5,
        description="Minimum time between alerts for same issue"
    )
    
    # Analysis
    max_analysis_iterations: int = Field(
        default=5,
        description="Maximum iterations for root cause analysis"
    )
    confidence_threshold: float = Field(
        default=0.7,
        description="Minimum confidence to proceed with action"
    )
    
    # Actions
    action_timeout_seconds: int = Field(
        default=300,
        description="Timeout for action execution"
    )
    max_retry_attempts: int = Field(
        default=3,
        description="Maximum retries for failed actions"
    )
    
    # Human approval
    approval_timeout_minutes: int = Field(
        default=30,
        description="How long to wait for human approval"
    )
    escalate_on_timeout: bool = Field(
        default=True,
        description="Escalate to PagerDuty if approval times out"
    )


# ============================================================================
# MAIN CONFIGURATION
# ============================================================================

class AgentConfig(BaseModel):
    """
    Complete configuration for the DevOps Incident Agent.
    
    This is the main configuration object that users fill out to connect
    the agent to their infrastructure.
    """
    
    # Data sources (what agent can SEE)
    prometheus: Optional[PrometheusConfig] = None
    grafana: Optional[GrafanaConfig] = None
    elasticsearch: Optional[ElasticsearchConfig] = None
    kubernetes: Optional[KubernetesConfig] = None
    
    # Notifications (how agent COMMUNICATES)
    slack: Optional[SlackConfig] = None
    pagerduty: Optional[PagerDutyConfig] = None
    
    # Permissions (what agent can DO)
    permissions: ActionPermissions = Field(default_factory=ActionPermissions)
    
    # Behavior tuning
    behavior: AgentBehaviorConfig = Field(default_factory=AgentBehaviorConfig)
    
    def get_configured_sources(self) -> List[str]:
        """Return list of configured data sources."""
        sources = []
        if self.prometheus:
            sources.append("prometheus")
        if self.grafana:
            sources.append("grafana")
        if self.elasticsearch:
            sources.append("elasticsearch")
        if self.kubernetes:
            sources.append("kubernetes")
        return sources
    
    def get_configured_notifications(self) -> List[str]:
        """Return list of configured notification channels."""
        channels = []
        if self.slack:
            channels.append("slack")
        if self.pagerduty:
            channels.append("pagerduty")
        return channels
```

**1.6 Create Configuration Loader**

Create `src/config/loader.py`:
```python
"""
Configuration loader that reads from files and environment variables.
"""

import os
from pathlib import Path
from typing import Optional
import yaml
from dotenv import load_dotenv

from .schema import AgentConfig


def load_config(
    config_path: Optional[str] = None,
    env_file: Optional[str] = None
) -> AgentConfig:
    """
    Load configuration from file and environment variables.
    
    Priority (highest to lowest):
    1. Environment variables
    2. Config file
    3. Default values
    
    Args:
        config_path: Path to YAML config file
        env_file: Path to .env file
    
    Returns:
        Validated AgentConfig object
    """
    # Load environment variables
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()  # Load from default .env
    
    config_data = {}
    
    # Load from YAML file if provided
    if config_path and Path(config_path).exists():
        with open(config_path) as f:
            config_data = yaml.safe_load(f) or {}
    
    # Override with environment variables
    _apply_env_overrides(config_data)
    
    # Validate and return
    return AgentConfig(**config_data)


def _apply_env_overrides(config_data: dict) -> None:
    """Apply environment variable overrides to config."""
    
    env_mappings = {
        # Prometheus
        "PROMETHEUS_URL": ["prometheus", "url"],
        "PROMETHEUS_TOKEN": ["prometheus", "token"],
        "PROMETHEUS_USERNAME": ["prometheus", "username"],
        "PROMETHEUS_PASSWORD": ["prometheus", "password"],
        
        # Grafana
        "GRAFANA_URL": ["grafana", "url"],
        "GRAFANA_API_KEY": ["grafana", "api_key"],
        
        # Elasticsearch
        "ELASTICSEARCH_URL": ["elasticsearch", "url"],
        "ELASTICSEARCH_API_KEY": ["elasticsearch", "api_key"],
        
        # Slack
        "SLACK_BOT_TOKEN": ["slack", "bot_token"],
        "SLACK_APP_TOKEN": ["slack", "app_token"],
        "SLACK_INCIDENTS_CHANNEL": ["slack", "incidents_channel"],
        
        # PagerDuty
        "PAGERDUTY_API_KEY": ["pagerduty", "api_key"],
        "PAGERDUTY_SERVICE_ID": ["pagerduty", "service_id"],
    }
    
    for env_var, path in env_mappings.items():
        value = os.getenv(env_var)
        if value:
            _set_nested(config_data, path, value)


def _set_nested(data: dict, path: list, value: any) -> None:
    """Set a value in a nested dictionary."""
    for key in path[:-1]:
        data = data.setdefault(key, {})
    data[path[-1]] = value


# Example config file for users
EXAMPLE_CONFIG = """
# DevOps Incident Agent Configuration
# Copy this to config.yaml and fill in your values

# Data Sources - What the agent can monitor
prometheus:
  url: "https://prometheus.yourcompany.com"
  auth_type: "token"  # none, basic, token
  # token: "your-prometheus-token"  # Or use PROMETHEUS_TOKEN env var

grafana:
  url: "https://grafana.yourcompany.com"
  # api_key: "your-grafana-key"  # Or use GRAFANA_API_KEY env var

elasticsearch:
  url: "https://elasticsearch.yourcompany.com:9200"
  index_pattern: "logs-*"

kubernetes:
  in_cluster: false  # Set true if running inside K8s
  kubeconfig_path: "~/.kube/config"
  context: "production"
  allowed_namespaces:
    - default
    - production
    - staging
  forbidden_namespaces:
    - kube-system

# Notifications - How the agent communicates
slack:
  # bot_token: "xoxb-..."  # Use SLACK_BOT_TOKEN env var
  incidents_channel: "#incidents"
  updates_channel: "#devops-updates"
  approver_user_ids:
    - "U1234567890"  # Your Slack user ID

# Permissions - What the agent can do
permissions:
  auto_approved:
    - query_metrics
    - search_logs
    - get_pod_status
  requires_approval:
    - restart_pod
    - scale_deployment
    - rollback_deployment
  forbidden:
    - delete_namespace
    - delete_pvc
  auto_approve_low_severity: false

# Agent Behavior
behavior:
  check_interval_seconds: 60
  approval_timeout_minutes: 30
  escalate_on_timeout: true
"""
```

#### Day 5: Basic LangGraph Skeleton

**1.7 Create State Schema**

Create `src/models/state.py`:
```python
"""
State definitions for the LangGraph agent.
"""

from typing import TypedDict, Optional, List, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel


class Alert(BaseModel):
    """Incoming alert from monitoring system."""
    id: str
    source: str  # prometheus, cloudwatch, etc.
    severity: Literal["low", "medium", "high", "critical"]
    service: str
    message: str
    labels: Dict[str, str] = {}
    timestamp: datetime


class Action(BaseModel):
    """A remediation action to be executed."""
    id: str
    type: str  # restart_pod, scale_deployment, etc.
    target: str  # What to act on
    parameters: Dict[str, Any] = {}
    requires_approval: bool = True
    risk_level: Literal["low", "medium", "high"]


class ActionResult(BaseModel):
    """Result of executing an action."""
    action_id: str
    success: bool
    message: str
    timestamp: datetime
    details: Dict[str, Any] = {}


class IncidentState(TypedDict, total=False):
    """
    Complete state for an incident investigation.
    This is passed between all agents in the graph.
    """
    
    # === Incident Identity ===
    incident_id: str
    status: Literal[
        "new",
        "investigating", 
        "analyzing",
        "awaiting_approval",
        "executing",
        "verifying",
        "resolved",
        "failed",
        "escalated"
    ]
    
    # === Alert Information ===
    alert: Dict[str, Any]  # Original alert
    severity: Literal["low", "medium", "high", "critical"]
    
    # === Collected Data ===
    metrics: Dict[str, Any]  # From Monitor agent
    logs: List[str]  # Relevant log entries
    recent_deployments: List[Dict[str, Any]]
    affected_services: List[str]
    
    # === Analysis Results ===
    root_cause: str
    hypothesis: str
    confidence: float  # 0.0 - 1.0
    similar_incidents: List[Dict[str, Any]]
    
    # === Action Planning ===
    action_plan: List[Dict[str, Any]]  # List of Action objects
    current_action_index: int
    
    # === Approvals ===
    approval_requested: bool
    approval_request_time: str
    approvals: Dict[str, Any]  # {action_type: {approved: bool, by: str, at: str}}
    
    # === Execution ===
    actions_taken: List[Dict[str, Any]]  # List of ActionResult objects
    
    # === Communication ===
    messages_sent: List[Dict[str, Any]]
    slack_thread_ts: str  # Slack thread for this incident
    
    # === Control Flow ===
    next_agent: str
    iteration_count: int
    error: Optional[str]
    
    # === Timestamps ===
    created_at: str
    updated_at: str
    resolved_at: Optional[str]
```

**1.8 Create Basic Graph Structure**

Create `src/agents/graph.py`:
```python
"""
Main LangGraph definition for the incident response agent.
"""

from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from src.models.state import IncidentState


def supervisor_decision(state: IncidentState) -> str:
    """
    The supervisor's routing logic.
    Decides which agent should handle the next step.
    """
    status = state.get("status", "new")
    
    # New incident - gather data
    if status == "new" or not state.get("metrics"):
        return "monitor"
    
    # Have data but no analysis
    if not state.get("root_cause"):
        return "analyzer"
    
    # Have analysis - check if we need approval
    if state.get("action_plan") and not state.get("approval_requested"):
        severity = state.get("severity", "medium")
        if severity in ["high", "critical"]:
            return "request_approval"
        # Low/medium severity - auto-approve for now
        return "action"
    
    # Waiting for approval
    if state.get("approval_requested") and not state.get("approvals"):
        return "wait_for_approval"
    
    # Approved - execute actions
    if state.get("approvals") and state.get("status") != "resolved":
        return "action"
    
    # Actions taken - verify
    if state.get("actions_taken") and state.get("status") == "executing":
        return "monitor"  # Re-verify metrics
    
    # Resolved
    if state.get("status") == "resolved":
        return "notify_resolution"
    
    return END


# Placeholder node functions (to be implemented in later phases)
def monitor_node(state: IncidentState) -> IncidentState:
    """Monitor agent: Gather metrics and logs."""
    print("[Monitor] Gathering infrastructure data...")
    return {
        **state,
        "status": "investigating",
        "metrics": {"placeholder": "to be implemented"},
        "logs": ["placeholder log entry"],
    }


def analyzer_node(state: IncidentState) -> IncidentState:
    """Analyzer agent: Perform root cause analysis."""
    print("[Analyzer] Analyzing root cause...")
    return {
        **state,
        "status": "analyzing",
        "root_cause": "Placeholder root cause",
        "confidence": 0.85,
        "action_plan": [
            {
                "id": "action-1",
                "type": "restart_pod",
                "target": "api-gateway",
                "requires_approval": True,
                "risk_level": "medium"
            }
        ]
    }


def request_approval_node(state: IncidentState) -> IncidentState:
    """Request human approval for actions."""
    print("[Comms] Requesting approval...")
    return {
        **state,
        "status": "awaiting_approval",
        "approval_requested": True,
    }


def action_node(state: IncidentState) -> IncidentState:
    """Action agent: Execute remediation."""
    print("[Action] Executing actions...")
    return {
        **state,
        "status": "resolved",
        "actions_taken": [{"action_id": "action-1", "success": True}],
    }


def notify_resolution_node(state: IncidentState) -> IncidentState:
    """Notify about resolution."""
    print("[Comms] Notifying resolution...")
    return state


def build_graph():
    """Build the main incident response graph."""
    
    # Create the graph
    graph = StateGraph(IncidentState)
    
    # Add nodes
    graph.add_node("supervisor", lambda s: s)  # Pass-through, routing only
    graph.add_node("monitor", monitor_node)
    graph.add_node("analyzer", analyzer_node)
    graph.add_node("request_approval", request_approval_node)
    graph.add_node("action", action_node)
    graph.add_node("notify_resolution", notify_resolution_node)
    
    # Entry point
    graph.add_edge(START, "supervisor")
    
    # Supervisor routes to appropriate agent
    graph.add_conditional_edges(
        "supervisor",
        supervisor_decision,
        {
            "monitor": "monitor",
            "analyzer": "analyzer",
            "request_approval": "request_approval",
            "action": "action",
            "notify_resolution": "notify_resolution",
            "wait_for_approval": END,  # Will be interrupted
            END: END,
        }
    )
    
    # All agents return to supervisor for next decision
    graph.add_edge("monitor", "supervisor")
    graph.add_edge("analyzer", "supervisor")
    graph.add_edge("request_approval", END)  # Pauses for human
    graph.add_edge("action", "supervisor")
    graph.add_edge("notify_resolution", END)
    
    # Compile with memory checkpointer (for development)
    memory = MemorySaver()
    return graph.compile(checkpointer=memory)


# Quick test
if __name__ == "__main__":
    from uuid import uuid4
    
    graph = build_graph()
    
    # Create test incident
    initial_state = {
        "incident_id": str(uuid4()),
        "status": "new",
        "alert": {
            "id": "alert-123",
            "source": "prometheus",
            "severity": "high",
            "service": "api-gateway",
            "message": "High CPU usage detected"
        },
        "severity": "high",
    }
    
    # Run the graph
    config = {"configurable": {"thread_id": initial_state["incident_id"]}}
    
    for event in graph.stream(initial_state, config):
        print(f"Event: {event}")
    
    print("\n✅ Basic graph working!")
```

#### Day 6-7: Docker Development Setup

**1.9 Create Docker Configuration**

Create `docker/Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY config/ ./config/

# Create non-root user
RUN useradd -m agent && chown -R agent:agent /app
USER agent

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the agent
CMD ["python", "-m", "src.main"]
```

Create `docker/docker-compose.yml`:
```yaml
version: '3.8'

services:
  # ==========================================================================
  # CORE SERVICES
  # ==========================================================================
  
  agent:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    container_name: incident-agent
    environment:
      - POSTGRES_URL=postgresql://postgres:postgres@postgres:5432/incident_agent
      - REDIS_URL=redis://redis:6379/0
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - ENVIRONMENT=development
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ../src:/app/src:ro  # Hot reload in dev
      - ../config:/app/config:ro
    networks:
      - agent-network

  # ==========================================================================
  # DATABASES
  # ==========================================================================
  
  postgres:
    image: postgres:16-alpine
    container_name: incident-postgres
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=incident_agent
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./init-db.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - agent-network

  redis:
    image: redis:7-alpine
    container_name: incident-redis
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - agent-network

  # ==========================================================================
  # MONITORING STACK (Local Development)
  # ==========================================================================
  
  prometheus:
    image: prom/prometheus:v2.48.0
    container_name: incident-prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    networks:
      - agent-network

  grafana:
    image: grafana/grafana:10.2.0
    container_name: incident-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
      - GF_USERS_ALLOW_SIGN_UP=false
    volumes:
      - grafana-data:/var/lib/grafana
      - ./grafana/provisioning:/etc/grafana/provisioning
    depends_on:
      - prometheus
    networks:
      - agent-network

  # ==========================================================================
  # VECTOR DATABASE
  # ==========================================================================
  
  qdrant:
    image: qdrant/qdrant:v1.7.0
    container_name: incident-qdrant
    ports:
      - "6333:6333"
    volumes:
      - qdrant-data:/qdrant/storage
    networks:
      - agent-network

volumes:
  postgres-data:
  redis-data:
  prometheus-data:
  grafana-data:
  qdrant-data:

networks:
  agent-network:
    driver: bridge
```

Create `docker/init-db.sql`:
```sql
-- Initialize database for LangGraph checkpointing and agent state

-- Checkpoints table (for LangGraph)
CREATE TABLE IF NOT EXISTS checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    type TEXT,
    checkpoint JSONB NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

-- Checkpoint writes table
CREATE TABLE IF NOT EXISTS checkpoint_writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    type TEXT,
    value JSONB,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);

-- Incidents table (for our application)
CREATE TABLE IF NOT EXISTS incidents (
    id UUID PRIMARY KEY,
    status TEXT NOT NULL,
    severity TEXT NOT NULL,
    alert_data JSONB NOT NULL,
    root_cause TEXT,
    resolution TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP WITH TIME ZONE
);

-- Actions log
CREATE TABLE IF NOT EXISTS action_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID REFERENCES incidents(id),
    action_type TEXT NOT NULL,
    target TEXT NOT NULL,
    parameters JSONB,
    approved_by TEXT,
    result JSONB,
    executed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Approvals table
CREATE TABLE IF NOT EXISTS approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    incident_id UUID REFERENCES incidents(id),
    action_type TEXT NOT NULL,
    requested_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    approved BOOLEAN,
    approved_by TEXT,
    approved_at TIMESTAMP WITH TIME ZONE,
    notes TEXT
);

-- Create indexes
CREATE INDEX idx_incidents_status ON incidents(status);
CREATE INDEX idx_incidents_created_at ON incidents(created_at);
CREATE INDEX idx_checkpoints_thread_id ON checkpoints(thread_id);
```

Create `docker/prometheus.yml`:
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets: []

scrape_configs:
  # Prometheus itself
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # Our agent (when we add metrics)
  - job_name: 'incident-agent'
    static_configs:
      - targets: ['agent:8000']
    metrics_path: '/metrics'

  # Example: scrape a demo application
  # - job_name: 'demo-app'
  #   static_configs:
  #     - targets: ['demo-app:8080']
```

### ✅ Phase 1 Checklist

- [ ] Project directory structure created
- [ ] Virtual environment set up
- [ ] Dependencies installed
- [ ] Configuration schema defined (`src/config/schema.py`)
- [ ] Configuration loader implemented (`src/config/loader.py`)
- [ ] State models defined (`src/models/state.py`)
- [ ] Basic LangGraph skeleton working (`src/agents/graph.py`)
- [ ] Docker Compose environment ready
- [ ] PostgreSQL and Redis running
- [ ] Prometheus and Grafana accessible
- [ ] Can run: `python -m src.agents.graph` without errors

### 🧪 Phase 1 Verification

```bash
# Test configuration loading
python -c "from src.config.loader import load_config; print(load_config())"

# Test basic graph
python -m src.agents.graph

# Start Docker environment
cd docker
docker-compose up -d

# Verify services
curl http://localhost:9090/-/healthy  # Prometheus
curl http://localhost:3000/api/health  # Grafana
docker exec incident-postgres pg_isready  # PostgreSQL
docker exec incident-redis redis-cli ping  # Redis
```

---

## Phase 2: Agent Development (Week 2)

### 🎯 Goals
- Implement Monitor Agent with real tools
- Implement Analyzer Agent with LLM reasoning
- Implement Action Agent with safety checks
- Create tool abstractions

### 📋 Tasks

#### Day 1-2: Monitor Agent

**2.1 Create Prometheus Tools**

Create `src/tools/prometheus.py`:
```python
"""
Prometheus query tools for the Monitor agent.
"""

import httpx
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pydantic import BaseModel

from src.config.schema import PrometheusConfig


class MetricResult(BaseModel):
    """Result from a Prometheus query."""
    metric_name: str
    labels: Dict[str, str]
    values: List[tuple]  # [(timestamp, value), ...]
    current_value: Optional[float]


class PrometheusClient:
    """Client for querying Prometheus."""
    
    def __init__(self, config: PrometheusConfig):
        self.config = config
        self.base_url = str(config.url).rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with auth."""
        if self._client is None:
            headers = {}
            auth = None
            
            if self.config.auth_type == "token" and self.config.token:
                headers["Authorization"] = f"Bearer {self.config.token.get_secret_value()}"
            elif self.config.auth_type == "basic":
                auth = (
                    self.config.username,
                    self.config.password.get_secret_value() if self.config.password else ""
                )
            
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                auth=auth,
                timeout=30.0
            )
        
        return self._client
    
    async def query(self, promql: str) -> Dict[str, Any]:
        """
        Execute an instant query.
        
        Args:
            promql: PromQL query string
        
        Returns:
            Query result with metric data
        """
        client = await self._get_client()
        response = await client.get(
            "/api/v1/query",
            params={"query": promql}
        )
        response.raise_for_status()
        return response.json()
    
    async def query_range(
        self,
        promql: str,
        start: datetime = None,
        end: datetime = None,
        step: str = "1m"
    ) -> Dict[str, Any]:
        """
        Execute a range query.
        
        Args:
            promql: PromQL query string
            start: Start time (default: 1 hour ago)
            end: End time (default: now)
            step: Query resolution step
        
        Returns:
            Query result with time series data
        """
        if end is None:
            end = datetime.utcnow()
        if start is None:
            start = end - timedelta(hours=1)
        
        client = await self._get_client()
        response = await client.get(
            "/api/v1/query_range",
            params={
                "query": promql,
                "start": start.isoformat() + "Z",
                "end": end.isoformat() + "Z",
                "step": step
            }
        )
        response.raise_for_status()
        return response.json()
    
    async def get_alerts(self) -> List[Dict[str, Any]]:
        """Get currently firing alerts."""
        client = await self._get_client()
        response = await client.get("/api/v1/alerts")
        response.raise_for_status()
        data = response.json()
        return data.get("data", {}).get("alerts", [])
    
    async def get_targets(self) -> Dict[str, Any]:
        """Get scrape targets and their health."""
        client = await self._get_client()
        response = await client.get("/api/v1/targets")
        response.raise_for_status()
        return response.json()
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None


# Tool functions for LangGraph
async def query_prometheus_metrics(
    query: str,
    time_range: str = "1h",
    config: PrometheusConfig = None
) -> Dict[str, Any]:
    """
    Query Prometheus metrics.
    
    Args:
        query: PromQL query (e.g., 'rate(http_requests_total[5m])')
        time_range: How far back to look (e.g., '1h', '30m', '6h')
        config: Prometheus configuration
    
    Returns:
        Dict containing metric values and summary
    """
    client = PrometheusClient(config)
    
    try:
        # Parse time range
        hours = 1
        if time_range.endswith("h"):
            hours = int(time_range[:-1])
        elif time_range.endswith("m"):
            hours = int(time_range[:-1]) / 60
        
        end = datetime.utcnow()
        start = end - timedelta(hours=hours)
        
        result = await client.query_range(query, start, end)
        
        # Process results
        data = result.get("data", {})
        results = data.get("result", [])
        
        processed = []
        for series in results:
            metric = series.get("metric", {})
            values = series.get("values", [])
            
            if values:
                current = float(values[-1][1]) if values[-1][1] != "NaN" else None
                avg = sum(float(v[1]) for v in values if v[1] != "NaN") / len(values)
                max_val = max(float(v[1]) for v in values if v[1] != "NaN")
                min_val = min(float(v[1]) for v in values if v[1] != "NaN")
            else:
                current = avg = max_val = min_val = None
            
            processed.append({
                "metric": metric,
                "current": current,
                "average": avg,
                "max": max_val,
                "min": min_val,
                "data_points": len(values)
            })
        
        return {
            "query": query,
            "time_range": time_range,
            "results": processed,
            "summary": f"Found {len(processed)} time series"
        }
    
    finally:
        await client.close()


async def get_prometheus_alerts(config: PrometheusConfig = None) -> List[Dict[str, Any]]:
    """
    Get currently firing Prometheus alerts.
    
    Returns:
        List of active alerts with details
    """
    client = PrometheusClient(config)
    
    try:
        alerts = await client.get_alerts()
        
        return [
            {
                "name": alert.get("labels", {}).get("alertname"),
                "severity": alert.get("labels", {}).get("severity", "unknown"),
                "state": alert.get("state"),
                "service": alert.get("labels", {}).get("service", "unknown"),
                "message": alert.get("annotations", {}).get("summary", ""),
                "description": alert.get("annotations", {}).get("description", ""),
                "started_at": alert.get("activeAt"),
                "labels": alert.get("labels", {})
            }
            for alert in alerts
        ]
    
    finally:
        await client.close()
```

**2.2 Create Kubernetes Tools**

Create `src/tools/kubernetes.py`:
```python
"""
Kubernetes tools for the Monitor and Action agents.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timezone

from src.config.schema import KubernetesConfig


class KubernetesClient:
    """Client for interacting with Kubernetes."""
    
    def __init__(self, config: KubernetesConfig):
        self.config = config
        self._api_client = None
        self._core_v1 = None
        self._apps_v1 = None
    
    def _init_client(self):
        """Initialize Kubernetes client."""
        from kubernetes import client, config as k8s_config
        
        if self.config.in_cluster:
            k8s_config.load_incluster_config()
        elif self.config.kubeconfig_path:
            k8s_config.load_kube_config(
                config_file=self.config.kubeconfig_path,
                context=self.config.context
            )
        else:
            k8s_config.load_kube_config(context=self.config.context)
        
        self._core_v1 = client.CoreV1Api()
        self._apps_v1 = client.AppsV1Api()
    
    @property
    def core_v1(self):
        if self._core_v1 is None:
            self._init_client()
        return self._core_v1
    
    @property
    def apps_v1(self):
        if self._apps_v1 is None:
            self._init_client()
        return self._apps_v1
    
    def _check_namespace_access(self, namespace: str) -> bool:
        """Check if namespace is accessible."""
        if namespace in self.config.forbidden_namespaces:
            raise PermissionError(f"Access to namespace '{namespace}' is forbidden")
        if self.config.allowed_namespaces and namespace not in self.config.allowed_namespaces:
            raise PermissionError(f"Namespace '{namespace}' is not in allowed list")
        return True
    
    async def get_pods(
        self,
        namespace: str,
        label_selector: str = None
    ) -> List[Dict[str, Any]]:
        """Get pods in a namespace."""
        self._check_namespace_access(namespace)
        
        pods = self.core_v1.list_namespaced_pod(
            namespace=namespace,
            label_selector=label_selector
        )
        
        result = []
        for pod in pods.items:
            # Calculate restarts
            restarts = 0
            container_statuses = []
            
            if pod.status.container_statuses:
                for cs in pod.status.container_statuses:
                    restarts += cs.restart_count
                    container_statuses.append({
                        "name": cs.name,
                        "ready": cs.ready,
                        "restarts": cs.restart_count,
                        "state": self._get_container_state(cs.state)
                    })
            
            result.append({
                "name": pod.metadata.name,
                "namespace": pod.metadata.namespace,
                "phase": pod.status.phase,
                "restarts": restarts,
                "containers": container_statuses,
                "node": pod.spec.node_name,
                "ip": pod.status.pod_ip,
                "created_at": pod.metadata.creation_timestamp.isoformat() if pod.metadata.creation_timestamp else None,
                "labels": pod.metadata.labels or {}
            })
        
        return result
    
    def _get_container_state(self, state) -> str:
        """Extract container state string."""
        if state.running:
            return "running"
        elif state.waiting:
            return f"waiting: {state.waiting.reason}"
        elif state.terminated:
            return f"terminated: {state.terminated.reason}"
        return "unknown"
    
    async def get_deployments(
        self,
        namespace: str,
        label_selector: str = None
    ) -> List[Dict[str, Any]]:
        """Get deployments in a namespace."""
        self._check_namespace_access(namespace)
        
        deployments = self.apps_v1.list_namespaced_deployment(
            namespace=namespace,
            label_selector=label_selector
        )
        
        result = []
        for dep in deployments.items:
            result.append({
                "name": dep.metadata.name,
                "namespace": dep.metadata.namespace,
                "replicas": {
                    "desired": dep.spec.replicas,
                    "ready": dep.status.ready_replicas or 0,
                    "available": dep.status.available_replicas or 0,
                    "unavailable": dep.status.unavailable_replicas or 0
                },
                "image": dep.spec.template.spec.containers[0].image if dep.spec.template.spec.containers else None,
                "created_at": dep.metadata.creation_timestamp.isoformat() if dep.metadata.creation_timestamp else None,
                "labels": dep.metadata.labels or {}
            })
        
        return result
    
    async def get_recent_events(
        self,
        namespace: str,
        involved_object: str = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get recent Kubernetes events."""
        self._check_namespace_access(namespace)
        
        field_selector = None
        if involved_object:
            field_selector = f"involvedObject.name={involved_object}"
        
        events = self.core_v1.list_namespaced_event(
            namespace=namespace,
            field_selector=field_selector,
            limit=limit
        )
        
        # Sort by last timestamp
        sorted_events = sorted(
            events.items,
            key=lambda e: e.last_timestamp or e.event_time or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True
        )
        
        return [
            {
                "type": event.type,
                "reason": event.reason,
                "message": event.message,
                "object": f"{event.involved_object.kind}/{event.involved_object.name}",
                "count": event.count,
                "first_seen": event.first_timestamp.isoformat() if event.first_timestamp else None,
                "last_seen": event.last_timestamp.isoformat() if event.last_timestamp else None
            }
            for event in sorted_events[:limit]
        ]
    
    # === Action Methods (require approval) ===
    
    async def restart_deployment(
        self,
        name: str,
        namespace: str
    ) -> Dict[str, Any]:
        """
        Restart a deployment by updating its annotation.
        This triggers a rolling restart.
        """
        self._check_namespace_access(namespace)
        
        # Patch the deployment with a restart annotation
        now = datetime.utcnow().isoformat()
        body = {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "kubectl.kubernetes.io/restartedAt": now
                        }
                    }
                }
            }
        }
        
        self.apps_v1.patch_namespaced_deployment(
            name=name,
            namespace=namespace,
            body=body
        )
        
        return {
            "action": "restart_deployment",
            "deployment": name,
            "namespace": namespace,
            "triggered_at": now,
            "status": "initiated"
        }
    
    async def scale_deployment(
        self,
        name: str,
        namespace: str,
        replicas: int
    ) -> Dict[str, Any]:
        """Scale a deployment to specified replicas."""
        self._check_namespace_access(namespace)
        
        # Get current state
        deployment = self.apps_v1.read_namespaced_deployment(name, namespace)
        previous_replicas = deployment.spec.replicas
        
        # Scale
        body = {"spec": {"replicas": replicas}}
        self.apps_v1.patch_namespaced_deployment(
            name=name,
            namespace=namespace,
            body=body
        )
        
        return {
            "action": "scale_deployment",
            "deployment": name,
            "namespace": namespace,
            "previous_replicas": previous_replicas,
            "new_replicas": replicas,
            "status": "initiated"
        }
    
    async def rollback_deployment(
        self,
        name: str,
        namespace: str,
        revision: int = None
    ) -> Dict[str, Any]:
        """
        Roll back a deployment to previous revision.
        
        Note: This uses kubectl under the hood as the API doesn't
        have a direct rollback endpoint.
        """
        import subprocess
        
        self._check_namespace_access(namespace)
        
        cmd = ["kubectl", "rollout", "undo", f"deployment/{name}", "-n", namespace]
        if revision:
            cmd.extend(["--to-revision", str(revision)])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"Rollback failed: {result.stderr}")
        
        return {
            "action": "rollback_deployment",
            "deployment": name,
            "namespace": namespace,
            "to_revision": revision or "previous",
            "status": "initiated",
            "message": result.stdout.strip()
        }


# Tool functions for LangGraph
async def get_pod_status(
    namespace: str,
    label_selector: str = None,
    config: KubernetesConfig = None
) -> Dict[str, Any]:
    """
    Get status of pods in a namespace.
    
    Args:
        namespace: Kubernetes namespace
        label_selector: Optional label selector (e.g., 'app=api-gateway')
        config: Kubernetes configuration
    
    Returns:
        Dict with pod information and health summary
    """
    client = KubernetesClient(config)
    pods = await client.get_pods(namespace, label_selector)
    
    # Calculate summary
    total = len(pods)
    running = len([p for p in pods if p["phase"] == "Running"])
    failing = [p for p in pods if p["phase"] != "Running" or p["restarts"] > 5]
    
    return {
        "namespace": namespace,
        "total_pods": total,
        "running": running,
        "failing_count": len(failing),
        "failing_pods": failing,
        "all_pods": pods,
        "health": "healthy" if len(failing) == 0 else "degraded"
    }


async def get_deployment_status(
    namespace: str,
    name: str = None,
    config: KubernetesConfig = None
) -> Dict[str, Any]:
    """
    Get status of deployments.
    
    Args:
        namespace: Kubernetes namespace
        name: Specific deployment name (optional)
        config: Kubernetes configuration
    
    Returns:
        Deployment status information
    """
    client = KubernetesClient(config)
    
    if name:
        deployments = await client.get_deployments(namespace, f"app={name}")
    else:
        deployments = await client.get_deployments(namespace)
    
    return {
        "namespace": namespace,
        "deployments": deployments,
        "count": len(deployments)
    }
```

**2.3 Create Monitor Agent**

Create `src/agents/monitor.py`:
```python
"""
Monitor Agent: Gathers real-time infrastructure data.
"""

from typing import List, Dict, Any
from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

from src.config.schema import AgentConfig
from src.models.state import IncidentState
from src.tools.prometheus import query_prometheus_metrics, get_prometheus_alerts
from src.tools.kubernetes import get_pod_status, get_deployment_status


MONITOR_SYSTEM_PROMPT = """You are a DevOps monitoring specialist. Your job is to gather 
relevant data about infrastructure incidents.

Current Alert Information:
{alert_info}

Your tasks:
1. Query metrics relevant to this alert type
2. Check the health of affected services
3. Look for recent changes (deployments, scaling events)
4. Gather relevant logs if available
5. Identify any dependent services that might be affected

Be thorough but efficient. Focus on data that will help diagnose the root cause.

Available tools:
- query_metrics: Query Prometheus for metric data
- get_alerts: Get currently firing alerts
- get_pods: Get Kubernetes pod status
- get_deployments: Get deployment status

Return your findings in a structured format with:
- Key metrics observed
- Service health status
- Any anomalies detected
- Recent events that might be relevant
"""


def build_monitor_agent(config: AgentConfig):
    """Build the Monitor agent with configured tools."""
    
    # Create tools with config bound
    @tool
    async def query_metrics(query: str, time_range: str = "1h") -> Dict[str, Any]:
        """Query Prometheus metrics. Use PromQL syntax."""
        if not config.prometheus:
            return {"error": "Prometheus not configured"}
        return await query_prometheus_metrics(query, time_range, config.prometheus)
    
    @tool
    async def get_alerts() -> List[Dict[str, Any]]:
        """Get currently firing Prometheus alerts."""
        if not config.prometheus:
            return {"error": "Prometheus not configured"}
        return await get_prometheus_alerts(config.prometheus)
    
    @tool
    async def get_pods(namespace: str, label_selector: str = None) -> Dict[str, Any]:
        """Get Kubernetes pod status in a namespace."""
        if not config.kubernetes:
            return {"error": "Kubernetes not configured"}
        return await get_pod_status(namespace, label_selector, config.kubernetes)
    
    @tool
    async def get_deployments(namespace: str, name: str = None) -> Dict[str, Any]:
        """Get Kubernetes deployment status."""
        if not config.kubernetes:
            return {"error": "Kubernetes not configured"}
        return await get_deployment_status(namespace, name, config.kubernetes)
    
    tools = [query_metrics, get_alerts, get_pods, get_deployments]
    
    # Create the ReAct agent
    llm = ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0)
    
    agent = create_react_agent(
        model=llm,
        tools=tools,
        state_modifier=MONITOR_SYSTEM_PROMPT
    )
    
    return agent


async def run_monitor_agent(state: IncidentState, config: AgentConfig) -> IncidentState:
    """
    Run the Monitor agent to gather infrastructure data.
    
    Args:
        state: Current incident state
        config: Agent configuration
    
    Returns:
        Updated state with collected metrics and logs
    """
    from langchain_core.messages import HumanMessage
    
    agent = build_monitor_agent(config)
    
    # Format alert info for the agent
    alert = state.get("alert", {})
    alert_info = f"""
    Alert: {alert.get('message', 'Unknown')}
    Service: {alert.get('service', 'Unknown')}
    Severity: {alert.get('severity', 'Unknown')}
    Source: {alert.get('source', 'Unknown')}
    """
    
    # Run the agent
    result = await agent.ainvoke({
        "messages": [HumanMessage(content=f"Investigate this alert:\n{alert_info}")],
    })
    
    # Extract findings from agent's response
    # The last message should be the agent's summary
    findings = parse_monitor_findings(result["messages"][-1].content)
    
    return {
        **state,
        "status": "investigating",
        "metrics": findings.get("metrics", {}),
        "logs": findings.get("logs", []),
        "affected_services": findings.get("affected_services", []),
        "recent_deployments": findings.get("recent_deployments", []),
    }


def parse_monitor_findings(content: str) -> Dict[str, Any]:
    """Parse the agent's response into structured findings."""
    # This is a simple parser - in production, you might want
    # to have the agent return structured JSON
    return {
        "metrics": {"raw_response": content},
        "logs": [],
        "affected_services": [],
        "recent_deployments": [],
    }
```

#### Day 3-4: Analyzer Agent

**2.4 Create Analyzer Agent**

Create `src/agents/analyzer.py`:
```python
"""
Analyzer Agent: Performs root cause analysis.
"""

from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from src.config.schema import AgentConfig
from src.models.state import IncidentState


class RootCauseAnalysis(BaseModel):
    """Structured output for root cause analysis."""
    root_cause: str = Field(description="The identified root cause")
    confidence: float = Field(description="Confidence level 0-1")
    evidence: List[str] = Field(description="Evidence supporting the diagnosis")
    similar_incidents: List[Dict[str, Any]] = Field(default=[], description="Similar past incidents")
    recommended_actions: List[Dict[str, Any]] = Field(description="Recommended remediation actions")


ANALYZER_SYSTEM_PROMPT = """You are a senior Site Reliability Engineer performing root cause analysis.

You have access to:
- Metrics and logs collected by the monitoring system
- Historical incident database (via search_incidents tool)
- Runbooks and documentation (via search_runbooks tool)

Current Incident Data:
{incident_data}

Your task:
1. Analyze the collected metrics and logs
2. Identify patterns that indicate the root cause
3. Search for similar past incidents
4. Consult relevant runbooks
5. Propose remediation actions

Be thorough in your analysis. Consider:
- Recent changes (deployments, config changes)
- Resource exhaustion (CPU, memory, disk)
- Dependencies and cascading failures
- External factors (traffic spikes, third-party outages)

Structure your final response as:
- Root Cause: [Clear description of what's causing the issue]
- Confidence: [0-100%]
- Evidence: [Bullet points of supporting data]
- Recommended Actions: [Ordered list with risk levels]
"""


def build_analyzer_agent(config: AgentConfig):
    """Build the Analyzer agent."""
    
    @tool
    async def search_incidents(
        query: str,
        service: str = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search historical incidents for similar issues.
        
        Args:
            query: Description of the issue to search for
            service: Filter by service name
            limit: Maximum results to return
        """
        # TODO: Implement RAG search over incident database
        # For now, return placeholder
        return [
            {
                "incident_id": "INC-001",
                "title": "Similar CPU spike incident",
                "root_cause": "Memory leak in v2.1.0",
                "resolution": "Rolled back to v2.0.9",
                "date": "2024-01-15"
            }
        ]
    
    @tool
    async def search_runbooks(
        query: str,
        service: str = None
    ) -> List[Dict[str, Any]]:
        """
        Search runbooks for remediation procedures.
        
        Args:
            query: Description of the issue
            service: Specific service to find runbooks for
        """
        # TODO: Implement RAG search over runbooks
        return [
            {
                "title": "High CPU Remediation",
                "steps": [
                    "1. Check for memory leaks",
                    "2. Verify recent deployments",
                    "3. Consider scaling or rollback"
                ],
                "service": service or "general"
            }
        ]
    
    @tool
    async def correlate_metrics(
        primary_metric: str,
        secondary_metrics: List[str]
    ) -> Dict[str, Any]:
        """
        Find correlations between metrics.
        
        Args:
            primary_metric: The main metric showing the issue
            secondary_metrics: Other metrics to correlate with
        """
        # TODO: Implement actual correlation analysis
        return {
            "primary": primary_metric,
            "correlations": [
                {"metric": m, "correlation": 0.85}
                for m in secondary_metrics
            ]
        }
    
    tools = [search_incidents, search_runbooks, correlate_metrics]
    
    llm = ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0)
    
    agent = create_react_agent(
        model=llm,
        tools=tools,
        state_modifier=ANALYZER_SYSTEM_PROMPT
    )
    
    return agent


async def run_analyzer_agent(state: IncidentState, config: AgentConfig) -> IncidentState:
    """
    Run the Analyzer agent to determine root cause.
    """
    agent = build_analyzer_agent(config)
    
    # Prepare incident data for analysis
    incident_data = f"""
    Alert: {state.get('alert', {}).get('message', 'Unknown')}
    Service: {state.get('alert', {}).get('service', 'Unknown')}
    Severity: {state.get('severity', 'Unknown')}
    
    Collected Metrics:
    {state.get('metrics', {})}
    
    Relevant Logs:
    {state.get('logs', [])}
    
    Recent Deployments:
    {state.get('recent_deployments', [])}
    
    Affected Services:
    {state.get('affected_services', [])}
    """
    
    result = await agent.ainvoke({
        "messages": [HumanMessage(content=f"Analyze this incident:\n{incident_data}")]
    })
    
    # Parse the analysis
    analysis = parse_analysis(result["messages"][-1].content)
    
    return {
        **state,
        "status": "analyzing",
        "root_cause": analysis.get("root_cause", "Unknown"),
        "confidence": analysis.get("confidence", 0.5),
        "hypothesis": analysis.get("hypothesis", ""),
        "similar_incidents": analysis.get("similar_incidents", []),
        "action_plan": analysis.get("recommended_actions", []),
    }


def parse_analysis(content: str) -> Dict[str, Any]:
    """Parse the analyzer's response."""
    # Simple parsing - in production, use structured output
    return {
        "root_cause": "Extracted from agent response",
        "confidence": 0.85,
        "hypothesis": content,
        "similar_incidents": [],
        "recommended_actions": [
            {
                "id": "action-1",
                "type": "rollback_deployment",
                "target": "api-gateway",
                "parameters": {},
                "requires_approval": True,
                "risk_level": "medium",
                "description": "Roll back to previous version"
            }
        ]
    }
```

#### Day 5-7: Action Agent with Safety

**2.5 Create Action Agent**

Create `src/agents/action.py`:
```python
"""
Action Agent: Executes remediation with safety checks.
"""

from typing import Dict, Any, List
from functools import wraps
from datetime import datetime
import structlog

from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

from src.config.schema import AgentConfig, ActionPermissions
from src.models.state import IncidentState
from src.tools.kubernetes import KubernetesClient

logger = structlog.get_logger()


class ActionNotApprovedError(Exception):
    """Raised when an action hasn't been approved."""
    pass


class ActionForbiddenError(Exception):
    """Raised when an action is in the forbidden list."""
    pass


def require_approval(action_type: str):
    """Decorator that ensures action has been approved."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            state = kwargs.get("state")
            permissions = kwargs.get("permissions")
            
            # Check if action is forbidden
            if permissions and action_type in permissions.forbidden:
                raise ActionForbiddenError(
                    f"Action '{action_type}' is forbidden and cannot be executed"
                )
            
            # Check if action needs approval
            if permissions and action_type in permissions.requires_approval:
                approvals = state.get("approvals", {}) if state else {}
                if not approvals.get(action_type, {}).get("approved"):
                    raise ActionNotApprovedError(
                        f"Action '{action_type}' requires approval"
                    )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


ACTION_SYSTEM_PROMPT = """You are an automated remediation system for DevOps incidents.

CRITICAL SAFETY RULES:
1. ONLY execute actions that are in the approved action plan
2. VERIFY each action has been approved before executing
3. If an action fails, DO NOT retry without re-approval
4. Log every action with full details

Current Incident: {incident_id}
Severity: {severity}

Approved Action Plan:
{action_plan}

Approvals Received:
{approvals}

Execute the approved actions in order. Report the result of each action.
Stop immediately if any action fails.
"""


def build_action_agent(config: AgentConfig, state: IncidentState):
    """Build the Action agent with safety-wrapped tools."""
    
    k8s_client = KubernetesClient(config.kubernetes) if config.kubernetes else None
    permissions = config.permissions
    
    @tool
    @require_approval("restart_deployment")
    async def restart_deployment(
        name: str,
        namespace: str
    ) -> Dict[str, Any]:
        """
        Restart a Kubernetes deployment.
        
        Args:
            name: Deployment name
            namespace: Kubernetes namespace
        """
        if not k8s_client:
            return {"error": "Kubernetes not configured"}
        
        logger.info(
            "Executing restart_deployment",
            deployment=name,
            namespace=namespace,
            incident_id=state.get("incident_id")
        )
        
        result = await k8s_client.restart_deployment(name, namespace)
        
        logger.info(
            "restart_deployment completed",
            result=result
        )
        
        return result
    
    @tool
    @require_approval("scale_deployment")
    async def scale_deployment(
        name: str,
        namespace: str,
        replicas: int
    ) -> Dict[str, Any]:
        """
        Scale a Kubernetes deployment.
        
        Args:
            name: Deployment name
            namespace: Kubernetes namespace
            replicas: Target replica count
        """
        if not k8s_client:
            return {"error": "Kubernetes not configured"}
        
        # Safety check: don't scale to 0 without explicit flag
        if replicas == 0:
            return {
                "error": "Scaling to 0 replicas requires special approval",
                "action": "blocked"
            }
        
        logger.info(
            "Executing scale_deployment",
            deployment=name,
            namespace=namespace,
            replicas=replicas
        )
        
        result = await k8s_client.scale_deployment(name, namespace, replicas)
        return result
    
    @tool
    @require_approval("rollback_deployment")
    async def rollback_deployment(
        name: str,
        namespace: str,
        revision: int = None
    ) -> Dict[str, Any]:
        """
        Roll back a deployment to a previous version.
        
        Args:
            name: Deployment name
            namespace: Kubernetes namespace
            revision: Specific revision (optional, defaults to previous)
        """
        if not k8s_client:
            return {"error": "Kubernetes not configured"}
        
        logger.info(
            "Executing rollback_deployment",
            deployment=name,
            namespace=namespace,
            revision=revision
        )
        
        result = await k8s_client.rollback_deployment(name, namespace, revision)
        return result
    
    # Bind state and permissions to tools
    for t in [restart_deployment, scale_deployment, rollback_deployment]:
        t.func = lambda f=t.func: f(state=state, permissions=permissions)
    
    tools = [restart_deployment, scale_deployment, rollback_deployment]
    
    llm = ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0)
    
    prompt = ACTION_SYSTEM_PROMPT.format(
        incident_id=state.get("incident_id", "unknown"),
        severity=state.get("severity", "unknown"),
        action_plan=state.get("action_plan", []),
        approvals=state.get("approvals", {})
    )
    
    agent = create_react_agent(
        model=llm,
        tools=tools,
        state_modifier=prompt
    )
    
    return agent


async def run_action_agent(state: IncidentState, config: AgentConfig) -> IncidentState:
    """
    Run the Action agent to execute remediation.
    """
    from langchain_core.messages import HumanMessage
    
    agent = build_action_agent(config, state)
    
    action_plan = state.get("action_plan", [])
    if not action_plan:
        return {
            **state,
            "error": "No action plan to execute"
        }
    
    # Execute the action plan
    result = await agent.ainvoke({
        "messages": [HumanMessage(
            content=f"Execute the approved action plan: {action_plan}"
        )]
    })
    
    # Parse results
    actions_taken = parse_action_results(result["messages"][-1].content)
    
    # Determine if all actions succeeded
    all_success = all(a.get("success", False) for a in actions_taken)
    
    return {
        **state,
        "status": "resolved" if all_success else "failed",
        "actions_taken": actions_taken,
        "resolved_at": datetime.utcnow().isoformat() if all_success else None,
    }


def parse_action_results(content: str) -> List[Dict[str, Any]]:
    """Parse action execution results."""
    return [
        {
            "action_id": "action-1",
            "success": True,
            "message": "Action completed",
            "timestamp": datetime.utcnow().isoformat()
        }
    ]
```

### ✅ Phase 2 Checklist

- [ ] Prometheus client implemented (`src/tools/prometheus.py`)
- [ ] Kubernetes client implemented (`src/tools/kubernetes.py`)
- [ ] Monitor agent working with real tools
- [ ] Analyzer agent with LLM reasoning
- [ ] Action agent with safety decorators
- [ ] Permission checking working
- [ ] All agents can be tested independently
- [ ] Integration test: Monitor → Analyzer → Action flow

### 🧪 Phase 2 Verification

```bash
# Test Prometheus tools (requires running Prometheus)
python -c "
import asyncio
from src.tools.prometheus import PrometheusClient
from src.config.schema import PrometheusConfig

config = PrometheusConfig(url='http://localhost:9090')
client = PrometheusClient(config)

async def test():
    alerts = await client.get_alerts()
    print(f'Alerts: {alerts}')
    await client.close()

asyncio.run(test())
"

# Test full agent flow
python -c "
import asyncio
from src.agents.graph import build_graph

graph = build_graph()
# Run test incident...
"
```

---

## Phase 3: Human-in-the-Loop & Persistence (Week 3)

### 🎯 Goals
- Implement PostgreSQL checkpointing
- Add human approval interrupts
- Create Slack approval workflow
- Handle async approvals

### 📋 Tasks

#### Day 1-2: PostgreSQL Checkpointing

**3.1 Set Up PostgreSQL Checkpointer**

Create `src/persistence/checkpointer.py`:
```python
"""
PostgreSQL checkpointer for LangGraph state persistence.
"""

from langgraph.checkpoint.postgres import PostgresSaver
from sqlalchemy.ext.asyncio import create_async_engine
import os


def get_checkpointer() -> PostgresSaver:
    """
    Create a PostgreSQL checkpointer for durable state.
    
    This ensures the agent can:
    - Survive restarts
    - Resume interrupted incidents
    - Support time-travel debugging
    """
    postgres_url = os.getenv(
        "POSTGRES_URL",
        "postgresql://postgres:postgres@localhost:5432/incident_agent"
    )
    
    # Convert to async URL if needed
    if postgres_url.startswith("postgresql://"):
        async_url = postgres_url.replace("postgresql://", "postgresql+asyncpg://")
    else:
        async_url = postgres_url
    
    return PostgresSaver.from_conn_string(postgres_url)


async def setup_checkpointer_tables():
    """Initialize the checkpointer tables if they don't exist."""
    checkpointer = get_checkpointer()
    await checkpointer.setup()
```

**3.2 Update Graph with Persistence**

Update `src/agents/graph.py`:
```python
# Add to build_graph function

from src.persistence.checkpointer import get_checkpointer

def build_graph(use_persistence: bool = True):
    """Build the main incident response graph."""
    
    graph = StateGraph(IncidentState)
    
    # ... add nodes and edges ...
    
    # Compile with appropriate checkpointer
    if use_persistence:
        checkpointer = get_checkpointer()
    else:
        checkpointer = MemorySaver()
    
    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_approval"]  # Pause before approval node
    )
```

#### Day 3-5: Human Approval System

**3.3 Create Human Approval Node**

Create `src/agents/approval.py`:
```python
"""
Human-in-the-loop approval system.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from langgraph.types import interrupt

from src.models.state import IncidentState


async def human_approval_node(state: IncidentState) -> IncidentState:
    """
    Pause the graph and wait for human approval.
    
    This node uses LangGraph's interrupt() to pause execution.
    The graph resumes when a human provides input via the API.
    """
    
    # Prepare approval request data
    approval_request = {
        "incident_id": state.get("incident_id"),
        "severity": state.get("severity"),
        "root_cause": state.get("root_cause"),
        "confidence": state.get("confidence"),
        "action_plan": state.get("action_plan"),
        "requested_at": datetime.utcnow().isoformat(),
    }
    
    # This pauses the graph!
    # The graph will resume when someone calls graph.invoke() with the thread_id
    human_response = interrupt(value=approval_request)
    
    # Process the response when graph resumes
    decision = human_response.get("decision")
    
    if decision == "approve":
        # Mark all actions in the plan as approved
        approvals = {}
        for action in state.get("action_plan", []):
            approvals[action["type"]] = {
                "approved": True,
                "approved_by": human_response.get("user"),
                "approved_at": datetime.utcnow().isoformat(),
                "notes": human_response.get("notes", "")
            }
        
        return {
            **state,
            "status": "executing",
            "approvals": approvals,
        }
    
    elif decision == "reject":
        return {
            **state,
            "status": "rejected",
            "error": f"Rejected by {human_response.get('user')}: {human_response.get('reason', 'No reason provided')}",
        }
    
    elif decision == "modify":
        # Human provided a modified action plan
        return {
            **state,
            "action_plan": human_response.get("modified_plan", state.get("action_plan")),
            "approval_requested": False,  # Need to re-request approval
        }
    
    else:
        return {
            **state,
            "error": f"Unknown approval decision: {decision}",
        }
```

**3.4 Create Approval API Endpoints**

Create `src/api/approvals.py`:
```python
"""
API endpoints for human approvals.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

from src.agents.graph import build_graph
from src.persistence.checkpointer import get_checkpointer

router = APIRouter(prefix="/approvals", tags=["approvals"])


class ApprovalRequest(BaseModel):
    """Request to approve/reject an incident action."""
    incident_id: str
    decision: str  # "approve", "reject", "modify"
    user: str
    reason: Optional[str] = None
    notes: Optional[str] = None
    modified_plan: Optional[List[Dict[str, Any]]] = None


class PendingApproval(BaseModel):
    """A pending approval waiting for human input."""
    incident_id: str
    severity: str
    root_cause: str
    confidence: float
    action_plan: List[Dict[str, Any]]
    requested_at: str


@router.get("/pending")
async def get_pending_approvals() -> List[PendingApproval]:
    """
    Get all incidents waiting for approval.
    
    This queries the checkpointer for graphs that are
    paused at the human_approval node.
    """
    # TODO: Implement query to find paused graphs
    # This requires iterating through active threads
    return []


@router.post("/respond")
async def respond_to_approval(request: ApprovalRequest):
    """
    Respond to an approval request (approve/reject/modify).
    
    This resumes the paused graph with the human's decision.
    """
    graph = build_graph()
    
    config = {"configurable": {"thread_id": request.incident_id}}
    
    try:
        # Resume the graph with the human's response
        result = await graph.ainvoke(
            {
                "decision": request.decision,
                "user": request.user,
                "reason": request.reason,
                "notes": request.notes,
                "modified_plan": request.modified_plan,
            },
            config=config
        )
        
        return {
            "success": True,
            "incident_id": request.incident_id,
            "new_status": result.get("status"),
            "message": f"Approval {request.decision} processed"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{incident_id}")
async def get_approval_details(incident_id: str) -> PendingApproval:
    """Get details of a specific pending approval."""
    graph = build_graph()
    config = {"configurable": {"thread_id": incident_id}}
    
    # Get current state
    state = await graph.aget_state(config)
    
    if not state or not state.values:
        raise HTTPException(status_code=404, detail="Incident not found")
    
    values = state.values
    
    return PendingApproval(
        incident_id=incident_id,
        severity=values.get("severity", "unknown"),
        root_cause=values.get("root_cause", "Unknown"),
        confidence=values.get("confidence", 0),
        action_plan=values.get("action_plan", []),
        requested_at=values.get("approval_request_time", datetime.utcnow().isoformat())
    )
```

#### Day 6-7: Slack Integration

**3.5 Create Slack Bot**

Create `src/integrations/slack.py`:
```python
"""
Slack integration for notifications and approvals.
"""

from typing import Dict, Any, List, Optional
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse
import structlog

from src.config.schema import SlackConfig
from src.models.state import IncidentState

logger = structlog.get_logger()


class SlackBot:
    """Slack bot for incident notifications and approvals."""
    
    def __init__(self, config: SlackConfig):
        self.config = config
        self.web_client = AsyncWebClient(token=config.bot_token.get_secret_value())
        self._socket_client: Optional[SocketModeClient] = None
    
    async def send_incident_alert(
        self,
        state: IncidentState,
        channel: str = None
    ) -> Dict[str, Any]:
        """Send an incident alert to Slack."""
        channel = channel or self.config.incidents_channel
        
        severity_emoji = {
            "low": "🟢",
            "medium": "🟡",
            "high": "🟠",
            "critical": "🔴"
        }
        
        alert = state.get("alert", {})
        emoji = severity_emoji.get(state.get("severity", "medium"), "⚪")
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} Incident Detected",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Incident ID:*\n{state.get('incident_id', 'N/A')}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Severity:*\n{state.get('severity', 'Unknown').upper()}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Service:*\n{alert.get('service', 'Unknown')}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Status:*\n{state.get('status', 'Unknown')}"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Alert:*\n{alert.get('message', 'No details')}"
                }
            }
        ]
        
        response = await self.web_client.chat_postMessage(
            channel=channel,
            text=f"Incident detected: {alert.get('message', 'Unknown')}",
            blocks=blocks
        )
        
        return {
            "channel": channel,
            "ts": response["ts"],
            "thread_ts": response["ts"]
        }
    
    async def request_approval(
        self,
        state: IncidentState,
        thread_ts: str = None
    ) -> Dict[str, Any]:
        """Send an approval request with interactive buttons."""
        channel = self.config.incidents_channel
        incident_id = state.get("incident_id", "unknown")
        
        # Build action plan text
        action_plan = state.get("action_plan", [])
        actions_text = "\n".join([
            f"• {a.get('type')}: {a.get('target')} ({a.get('risk_level', 'unknown')} risk)"
            for a in action_plan
        ])
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚨 Action Approval Required",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Root Cause:*\n{state.get('root_cause', 'Unknown')}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Confidence:* {int(state.get('confidence', 0) * 100)}%"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Proposed Actions:*\n{actions_text}"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "✅ Approve",
                            "emoji": True
                        },
                        "style": "primary",
                        "action_id": f"approve_{incident_id}",
                        "value": incident_id
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "❌ Reject",
                            "emoji": True
                        },
                        "style": "danger",
                        "action_id": f"reject_{incident_id}",
                        "value": incident_id
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "✏️ Modify",
                            "emoji": True
                        },
                        "action_id": f"modify_{incident_id}",
                        "value": incident_id
                    }
                ]
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Incident ID: {incident_id} | Timeout: 30 minutes"
                    }
                ]
            }
        ]
        
        response = await self.web_client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text="Action approval required",
            blocks=blocks
        )
        
        return {
            "channel": channel,
            "ts": response["ts"],
            "thread_ts": thread_ts or response["ts"]
        }
    
    async def send_resolution(
        self,
        state: IncidentState,
        thread_ts: str = None
    ) -> Dict[str, Any]:
        """Send incident resolution notification."""
        channel = self.config.incidents_channel
        
        actions_taken = state.get("actions_taken", [])
        actions_text = "\n".join([
            f"• {a.get('action_id')}: {'✅' if a.get('success') else '❌'}"
            for a in actions_taken
        ])
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "✅ Incident Resolved",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Incident ID:*\n{state.get('incident_id', 'N/A')}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Resolution Time:*\n{self._calculate_duration(state)}"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Root Cause:*\n{state.get('root_cause', 'Unknown')}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Actions Taken:*\n{actions_text}"
                }
            }
        ]
        
        response = await self.web_client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text="Incident resolved",
            blocks=blocks
        )
        
        return {"channel": channel, "ts": response["ts"]}
    
    def _calculate_duration(self, state: IncidentState) -> str:
        """Calculate incident duration."""
        from datetime import datetime
        
        created = state.get("created_at")
        resolved = state.get("resolved_at")
        
        if not created or not resolved:
            return "Unknown"
        
        try:
            start = datetime.fromisoformat(created.replace("Z", "+00:00"))
            end = datetime.fromisoformat(resolved.replace("Z", "+00:00"))
            duration = end - start
            
            minutes = int(duration.total_seconds() / 60)
            if minutes < 60:
                return f"{minutes} minutes"
            else:
                hours = minutes // 60
                mins = minutes % 60
                return f"{hours}h {mins}m"
        except Exception:
            return "Unknown"
```

**3.6 Create Slack Event Handler**

Create `src/api/slack_events.py`:
```python
"""
Slack event handlers for interactive components.
"""

from fastapi import APIRouter, Request, HTTPException
from slack_sdk.signature import SignatureVerifier
import json
import os

from src.agents.graph import build_graph

router = APIRouter(prefix="/slack", tags=["slack"])

signature_verifier = SignatureVerifier(
    signing_secret=os.getenv("SLACK_SIGNING_SECRET", "")
)


@router.post("/events")
async def handle_slack_events(request: Request):
    """Handle Slack events (URL verification, etc.)."""
    body = await request.body()
    
    # Verify request is from Slack
    if not signature_verifier.is_valid_request(body, request.headers):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    data = json.loads(body)
    
    # URL verification challenge
    if data.get("type") == "url_verification":
        return {"challenge": data["challenge"]}
    
    # Handle other events
    event = data.get("event", {})
    event_type = event.get("type")
    
    # Add event handlers as needed
    
    return {"ok": True}


@router.post("/actions")
async def handle_slack_actions(request: Request):
    """Handle Slack interactive components (button clicks)."""
    form_data = await request.form()
    payload = json.loads(form_data.get("payload", "{}"))
    
    # Verify signature
    # (In production, verify the request signature)
    
    action = payload.get("actions", [{}])[0]
    action_id = action.get("action_id", "")
    incident_id = action.get("value", "")
    user = payload.get("user", {})
    user_id = user.get("id")
    user_name = user.get("name")
    
    # Determine decision from action_id
    if action_id.startswith("approve_"):
        decision = "approve"
    elif action_id.startswith("reject_"):
        decision = "reject"
    elif action_id.startswith("modify_"):
        decision = "modify"
    else:
        return {"ok": False, "error": "Unknown action"}
    
    # Resume the graph with the decision
    graph = build_graph()
    config = {"configurable": {"thread_id": incident_id}}
    
    try:
        result = await graph.ainvoke(
            {
                "decision": decision,
                "user": user_name,
                "user_id": user_id,
            },
            config=config
        )
        
        # Update the Slack message to show the decision
        # (Would use Slack API to update the original message)
        
        return {
            "response_type": "in_channel",
            "text": f"✅ {decision.capitalize()} by @{user_name}"
        }
    
    except Exception as e:
        return {
            "response_type": "ephemeral",
            "text": f"Error processing approval: {str(e)}"
        }
```

### ✅ Phase 3 Checklist

- [ ] PostgreSQL checkpointer working
- [ ] Graph survives restarts
- [ ] Human approval node pauses graph
- [ ] Approval API endpoints working
- [ ] Slack bot sends incident alerts
- [ ] Slack approval buttons working
- [ ] Async approval flow tested end-to-end
- [ ] Graph resumes correctly after approval

### 🧪 Phase 3 Verification

```bash
# Test checkpoint persistence
python -c "
from src.agents.graph import build_graph

graph = build_graph(use_persistence=True)
# Create incident, verify it persists across restarts
"

# Test Slack integration (requires bot token)
python -c "
import asyncio
from src.integrations.slack import SlackBot
from src.config.schema import SlackConfig

config = SlackConfig(
    bot_token='xoxb-your-token',
    incidents_channel='#test-incidents'
)
bot = SlackBot(config)

asyncio.run(bot.send_incident_alert({
    'incident_id': 'test-123',
    'severity': 'high',
    'alert': {'message': 'Test alert', 'service': 'test-service'}
}))
"
```

---

## Phase 4: Monitoring & Alerting Integration (Week 4)

### 🎯 Goals
- Implement continuous monitoring loop
- Set up alert webhook receiver
- Create anomaly detection
- Integrate with Grafana dashboards

### 📋 Tasks

(Continue with detailed tasks for Phase 4...)

---

## Phase 5: Communication & Notifications (Week 5)

### 🎯 Goals
- Complete Slack integration
- Add PagerDuty escalation
- Implement Jira ticket creation
- Add email notifications

---

## Phase 6: Configuration UI (Week 6)

### 🎯 Goals
- Build FastAPI backend for configuration
- Create React frontend
- Implement connection testing
- Add permission management UI

---

## Phase 7: Production Hardening (Week 7)

### 🎯 Goals
- Add comprehensive error handling
- Implement retry logic
- Add circuit breakers
- Set up structured logging
- Add metrics and tracing

---

## Phase 8: Deployment & DevOps (Week 8)

### 🎯 Goals
- Create Kubernetes manifests
- Set up Helm charts
- Implement CI/CD pipeline
- Add monitoring dashboards
- Write documentation

---

## 📁 Project Structure

```
devops-incident-agent/
├── src/
│   ├── __init__.py
│   ├── main.py                 # Application entry point
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── graph.py            # Main LangGraph definition
│   │   ├── monitor.py          # Monitor agent
│   │   ├── analyzer.py         # Analyzer agent
│   │   ├── action.py           # Action agent
│   │   ├── comms.py            # Communications agent
│   │   └── approval.py         # Human approval node
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── prometheus.py       # Prometheus tools
│   │   ├── kubernetes.py       # Kubernetes tools
│   │   ├── elasticsearch.py    # Log search tools
│   │   └── actions.py          # Remediation tools
│   ├── config/
│   │   ├── __init__.py
│   │   ├── schema.py           # Configuration schema
│   │   └── loader.py           # Configuration loader
│   ├── models/
│   │   ├── __init__.py
│   │   └── state.py            # State definitions
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI app
│   │   ├── incidents.py        # Incident endpoints
│   │   ├── approvals.py        # Approval endpoints
│   │   ├── config.py           # Configuration endpoints
│   │   └── slack_events.py     # Slack webhook handlers
│   ├── integrations/
│   │   ├── __init__.py
│   │   ├── slack.py            # Slack bot
│   │   ├── pagerduty.py        # PagerDuty client
│   │   └── jira.py             # Jira client
│   ├── persistence/
│   │   ├── __init__.py
│   │   ├── checkpointer.py     # PostgreSQL checkpointer
│   │   └── repositories.py     # Database repositories
│   └── utils/
│       ├── __init__.py
│       ├── logging.py          # Structured logging
│       └── metrics.py          # Prometheus metrics
├── tests/
│   ├── unit/
│   │   ├── test_agents.py
│   │   ├── test_tools.py
│   │   └── test_config.py
│   └── integration/
│       ├── test_graph.py
│       └── test_api.py
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── prometheus.yml
│   └── init-db.sql
├── k8s/
│   ├── namespace.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   └── hpa.yaml
├── docs/
│   ├── images/
│   ├── architecture.md
│   ├── configuration.md
│   └── runbooks.md
├── config/
│   └── config.example.yaml
├── .env.example
├── .gitignore
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

---

## ⚙️ Configuration Guide

See `config/config.example.yaml` for a complete example configuration.

### Quick Start Configuration

1. Copy the example config:
   ```bash
   cp config/config.example.yaml config/config.yaml
   ```

2. Set environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. Start the services:
   ```bash
   cd docker
   docker-compose up -d
   ```

4. Test the connection:
   ```bash
   curl http://localhost:8000/health
   ```

---

## 📖 API Reference

### Incidents

- `POST /incidents` - Create a new incident
- `GET /incidents` - List all incidents
- `GET /incidents/{id}` - Get incident details
- `POST /incidents/{id}/cancel` - Cancel an incident

### Approvals

- `GET /approvals/pending` - Get pending approvals
- `POST /approvals/respond` - Respond to an approval
- `GET /approvals/{incident_id}` - Get approval details

### Configuration

- `GET /config` - Get current configuration
- `PUT /config` - Update configuration
- `POST /config/test` - Test connections

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest`
5. Submit a pull request

---

## 📄 License

MIT License - see LICENSE file for details.

---

## 🙏 Acknowledgments

- LangGraph team for the excellent framework
- Anthropic for Claude
- The DevOps community for inspiration

---

**Ready to start? Begin with [Phase 1](#phase-1-foundation--core-setup-week-1)!**