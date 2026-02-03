"""
Action Generation Node

Uses a hybrid approach:
1. GPT-4o generates intelligent, context-aware actions based on root cause analysis
2. Predefined templates provide fallback and validation
3. Actions from similar incidents inform recommendations

This ensures actions are both intelligent AND executable.
"""

from typing import Dict, Any, List
import json
import re

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from backend.config.settings import settings

# Load settings
MODEL = settings.MODEL
OPENAI_API_KEY = settings.OPENAI_API_KEY
MAX_ACTIONS = settings.MAX_ACTIONS
CONFIDENCE_THRESHOLD = settings.CONFIDENCE_THRESHOLD


# ============================================================================
# Valid Action Types Configuration
# ============================================================================


VALID_ACTION_TYPES = {
    "rollback": {
        "description": "Roll back to a previous deployment version",
        "risk_level": "medium",
        "common_parameters": ["to_revision", "target_version"],
    },
    "restart_pods": {
        "description": "Restart pods to clear state and refresh connections",
        "risk_level": "low",
        "common_parameters": ["rolling", "all_at_once"],
    },
    "scale_up": {
        "description": "Increase the number of replicas",
        "risk_level": "low",
        "common_parameters": ["replicas_increase", "target_replicas"],
    },
    "scale_down": {
        "description": "Decrease the number of replicas",
        "risk_level": "medium",
        "common_parameters": ["replicas_decrease", "target_replicas"],
    },
    "check_dependency": {
        "description": "Verify health of downstream services/dependencies",
        "risk_level": "none",
        "common_parameters": ["dependency_name", "check_type"],
    },
    "update_config": {
        "description": "Update configuration (ConfigMap, env vars, etc.)",
        "risk_level": "medium",
        "common_parameters": ["config_key", "new_value"],
    },
    "increase_resources": {
        "description": "Increase CPU/memory limits for pods",
        "risk_level": "low",
        "common_parameters": ["cpu_increase", "memory_increase"],
    },
    "decrease_resources": {
        "description": "Decrease CPU/memory limits for pods",
        "risk_level": "medium",
        "common_parameters": ["cpu_decrease", "memory_decrease"],
    },
    "enable_debug_logging": {
        "description": "Enable debug-level logging for investigation",
        "risk_level": "low",
        "common_parameters": ["duration_minutes", "log_level"],
    },
    "run_diagnostics": {
        "description": "Run diagnostic commands/scripts",
        "risk_level": "none",
        "common_parameters": ["diagnostic_type"],
    },
    "notify_oncall": {
        "description": "Escalate to on-call engineer",
        "risk_level": "none",
        "common_parameters": ["urgency", "message"],
    },
    "investigate": {
        "description": "Manual investigation required",
        "risk_level": "none",
        "common_parameters": ["investigation_areas"],
    },
}

# Pattern-to-action mappings (fallback suggestions)
PATTERN_ACTION_HINTS = {
    "oom_killed": ["rollback", "increase_resources", "restart_pods"],
    "high_memory": ["restart_pods", "scale_up", "increase_resources"],
    "high_cpu": ["scale_up", "rollback", "increase_resources"],
    "high_error_rate": ["rollback", "check_dependency", "restart_pods"],
    "high_latency": ["scale_up", "check_dependency", "increase_resources"],
    "crash_loop": ["rollback", "restart_pods", "check_dependency"],
    "connection_errors": ["restart_pods", "check_dependency", "scale_up"],
    "pod_failures": ["rollback", "restart_pods", "run_diagnostics"],
    "probe_failure": ["update_config", "increase_resources", "restart_pods"],
    "recent_deployment": ["rollback"],
    "timeout_errors": ["scale_up", "check_dependency", "update_config"],
    "error_spike": ["rollback", "check_dependency", "enable_debug_logging"],
}


# ============================================================================
# LLM-Based Action Generation
# ============================================================================


def _parse_json_from_response(content: str) -> Dict[str, Any]:
    """
    Extract and parse JSON from LLM response.
    Handles markdown code blocks and plain JSON.
    """
    # Try to find JSON in code blocks
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
    if json_match:
        json_str = json_match.group(1).strip()
    else:
        # Try to find raw JSON object
        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            json_str = json_match.group(0)
        else:
            return {}

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return {}


async def _generate_actions_with_llm(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Use GPT-4o to generate intelligent, context-aware actions.

    The LLM considers:
    - Root cause analysis
    - Similar incidents and their resolutions
    - Current patterns and severity
    - Service-specific context
    """
    alert = state.get("alert", {})
    patterns = state.get("patterns", [])
    root_cause = state.get("root_cause", "Unknown")
    confidence = state.get("confidence", 0.5)
    severity = state.get("severity", "medium")
    similar_incidents = state.get("similar_incidents", [])
    recent_deployments = state.get("recent_deployments", [])

    service = alert.get("service", "unknown-service")
    namespace = alert.get("namespace", "default")

    # Format patterns
    patterns_text = "\n".join(
        [f"- {p.get('type')}: {p.get('description', '')}" for p in patterns]
    )

    # Format similar incidents with resolutions
    if similar_incidents:
        similar_text = "\n".join(
            [
                f"- [{inc['id']}] (similarity: {inc['similarity']})\n"
                f"  Problem: {inc.get('title', '')}\n"
                f"  Resolution: {inc.get('resolution', 'N/A')}"
                for inc in similar_incidents[:3]
            ]
        )
    else:
        similar_text = "No similar past incidents found."

    # Format recent deployments
    if recent_deployments:
        deployments_text = "\n".join(
            [
                f"- {dep.get('name')}: {dep.get('image')} (revision {dep.get('revision')})"
                for dep in recent_deployments
            ]
        )
    else:
        deployments_text = "No recent deployments."

    # Format available action types
    action_types_list = list(VALID_ACTION_TYPES.keys())
    action_types_text = "\n".join(
        [
            f"- {action_type}: {info['description']} (risk: {info['risk_level']})"
            for action_type, info in VALID_ACTION_TYPES.items()
        ]
    )

    # Build prompt
    prompt = f"""You are a DevOps automation system generating remediation actions for a production incident.

## Incident Context
- **Service**: {service}
- **Namespace**: {namespace}
- **Severity**: {severity}
- **Alert**: {alert.get('alertname', 'Unknown')}
- **Message**: {alert.get('message', 'No message')}

## Root Cause Analysis
**Identified Root Cause**: {root_cause}
**Confidence**: {confidence * 100:.0f}%

## Detected Patterns
{patterns_text if patterns_text else "No patterns detected."}

## Similar Past Incidents & Resolutions
{similar_text}

## Recent Deployments
{deployments_text}

## Available Action Types
{action_types_text}

## Your Task
Based on the root cause analysis and similar incidents, recommend 1-3 remediation actions.

**Guidelines**:
1. Prioritize actions that directly address the root cause
2. Consider resolutions from similar incidents
3. Start with lower-risk actions when possible
4. If a recent deployment correlates with the issue, consider rollback
5. Set requires_approval to true for high/critical severity or medium/high risk actions

**IMPORTANT**: Only use action types from this list: {action_types_list}

Respond with ONLY a JSON object in this exact format:
```json
{{
  "actions": [
    {{
      "type": "action_type_here",
      "reason": "Why this action is recommended",
      "risk_level": "none|low|medium|high",
      "parameters": {{}},
      "expected_outcome": "What should happen after this action",
      "rollback_plan": "How to undo this action"
    }}
  ],
  "reasoning": "Brief explanation of why these actions were chosen",
  "requires_approval": true,
  "approval_reason": "Why approval is needed"
}}
```"""

    # Initialize LLM
    llm = ChatOpenAI(model=MODEL, temperature=0, api_key=OPENAI_API_KEY)

    response = await llm.ainvoke(
        [
            SystemMessage(
                content="You are an expert DevOps automation system. Generate safe, effective remediation actions. Always respond with valid JSON only."
            ),
            HumanMessage(content=prompt),
        ]
    )

    # Parse JSON response
    parsed = _parse_json_from_response(response.content)

    if not parsed or "actions" not in parsed:
        # Fallback if parsing fails
        print("[Analyzer] Failed to parse LLM response, using fallback")
        return _generate_actions_fallback(state)

    # Convert to output format
    actions = []
    for i, action in enumerate(parsed.get("actions", [])[:MAX_ACTIONS]):
        action_type = action.get("type", "investigate")

        # Validate action type
        if action_type not in VALID_ACTION_TYPES:
            action_type = "investigate"

        actions.append(
            {
                "action_id": str(i + 1),
                "type": action_type,
                "target": f"deployment/{service}",
                "target_namespace": namespace,
                "reason": action.get("reason", "Recommended action"),
                "risk_level": action.get("risk_level", "medium"),
                "parameters": action.get("parameters", {}),
                "expected_outcome": action.get("expected_outcome", "Issue mitigated"),
                "rollback_plan": action.get("rollback_plan", "Revert if needed"),
                "order": i + 1,
                "source": "llm",
            }
        )

    return {
        "recommended_actions": actions,
        "requires_approval": parsed.get("requires_approval", True),
        "actions_reasoning": parsed.get("reasoning", ""),
        "approval_reason": parsed.get("approval_reason", ""),
    }


# ============================================================================
# Fallback Rule-Based Action Generation
# ============================================================================


def _generate_actions_fallback(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fallback rule-based action generation when LLM is unavailable.
    Uses predefined pattern-to-action mappings.
    """
    patterns = state.get("patterns", [])
    similar_incidents = state.get("similar_incidents", [])
    alert = state.get("alert", {})
    confidence = state.get("confidence", 0.5)
    severity = state.get("severity", "medium")

    service = alert.get("service", "unknown-service")
    namespace = alert.get("namespace", "default")

    actions = []
    seen_types = set()
    action_id = 1

    # Collect suggested action types based on patterns
    suggested_types = []
    for pattern in patterns:
        pattern_type = pattern.get("type", "")
        if pattern_type in PATTERN_ACTION_HINTS:
            for action_type in PATTERN_ACTION_HINTS[pattern_type]:
                if action_type not in suggested_types:
                    suggested_types.append(action_type)

    # Generate actions from suggestions
    for action_type in suggested_types[:MAX_ACTIONS]:
        if action_type in seen_types:
            continue
        seen_types.add(action_type)

        action_info = VALID_ACTION_TYPES.get(action_type, {})
        actions.append(
            {
                "action_id": str(action_id),
                "type": action_type,
                "target": f"deployment/{service}",
                "target_namespace": namespace,
                "reason": action_info.get("description", "Recommended based on patterns"),
                "risk_level": action_info.get("risk_level", "medium"),
                "parameters": {},
                "expected_outcome": "Issue should be mitigated",
                "rollback_plan": "Revert the action if symptoms worsen",
                "order": action_id,
                "source": "fallback",
            }
        )
        action_id += 1

    # If similar incident found, prioritize its approach
    if similar_incidents and similar_incidents[0].get("similarity", 0) > 0.7:
        top_incident = similar_incidents[0]
        if actions:
            actions[0]["note"] = (
                f"Similar to {top_incident['id']}: {top_incident.get('resolution', '')[:100]}"
            )

    # Determine approval requirement
    requires_approval = (
        severity in ["high", "critical"]
        or confidence < CONFIDENCE_THRESHOLD
        or any(a["risk_level"] in ["medium", "high"] for a in actions)
    )

    # Default investigate action if nothing generated
    if not actions:
        actions.append(
            {
                "action_id": "1",
                "type": "investigate",
                "target": f"service/{service}",
                "target_namespace": namespace,
                "reason": "Manual investigation needed - no automatic remediation identified",
                "risk_level": "none",
                "parameters": {},
                "expected_outcome": "Root cause identified through manual investigation",
                "rollback_plan": "N/A",
                "order": 1,
                "source": "fallback",
            }
        )
        requires_approval = True

    return {
        "recommended_actions": actions,
        "requires_approval": requires_approval,
        "actions_reasoning": "Generated using pattern-based rules (fallback mode)",
        "approval_reason": "Fallback mode requires human verification" if requires_approval else "",
    }


# ============================================================================
# Main Node Function (Hybrid Approach)
# ============================================================================


async def generate_actions_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node 4: Generate recommended actions using hybrid approach.

    Strategy:
    1. Try LLM-based generation for intelligent, context-aware actions
    2. Fall back to rule-based generation if LLM unavailable
    3. Validate and enrich actions with predefined templates

    Args:
        state: Current analyzer state with patterns, root_cause, similar_incidents

    Returns:
        Updated state with recommended_actions, requires_approval
    """
    print("[Analyzer] Generating action recommendations...")

    use_llm = OPENAI_API_KEY is not None
    result = None

    if use_llm:
        try:
            print("[Analyzer] Using LLM for intelligent action generation...")
            result = await _generate_actions_with_llm(state)
        except Exception as e:
            print(f"[Analyzer] LLM action generation failed: {e}")
            print("[Analyzer] Falling back to rule-based generation...")
            result = _generate_actions_fallback(state)
    else:
        print("[Analyzer] No API key, using rule-based action generation...")
        result = _generate_actions_fallback(state)

    # Validate action types
    validated_actions = []
    for action in result.get("recommended_actions", []):
        if action["type"] in VALID_ACTION_TYPES:
            validated_actions.append(action)
        else:
            print(f"[Analyzer] Warning: Invalid action type '{action['type']}' filtered out")

    result["recommended_actions"] = validated_actions

    print(f"[Analyzer] Generated {len(validated_actions)} recommended actions")

    return result
