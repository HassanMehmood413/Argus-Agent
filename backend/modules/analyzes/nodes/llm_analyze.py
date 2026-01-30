from typing import Dict, Any
import os
import re

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from backend.config.settings import settings

MODEL = settings.MODEL
OPENAI_API_KEY = settings.OPENAI_API_KEY

async def llm_analyze_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node 3: Use GPT-4o to reason about root cause.

    This is where the AI performs root cause analysis based on:
    - Detected patterns from monitoring data
    - Similar past incidents from RAG
    - Current metrics, logs, and pod status

    Args:
        state: Current analyzer state with patterns and similar_incidents

    Returns:
        Updated state with root_cause, confidence, evidence, and analysis_reasoning
    """
    print("[Analyzer] Running LLM analysis with GPT-4o...")

    # Verify API key is available
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is required for LLM analysis")

    return await _analyze_with_gpt4o(state)


async def _analyze_with_gpt4o(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Perform analysis using GPT-4o.

    Args:
        state: Current analyzer state

    Returns:
        Analysis results including root_cause, confidence, evidence
    """
    # Extract state data
    alert = state.get("alert", {})
    patterns = state.get("patterns", [])
    similar_incidents = state.get("similar_incidents", [])
    metrics = state.get("metrics", {})
    logs = state.get("logs", [])
    pod_status = state.get("pod_status", {})

    # Format patterns for prompt
    patterns_text = "\n".join(
        [f"- {p.get('type')}: {p.get('description')}" for p in patterns]
    )
    if not patterns_text:
        patterns_text = "No patterns detected."

    # Format similar incidents
    if similar_incidents:
        similar_text = "\n".join(
            [
                f"- [{inc['id']}] (similarity: {inc['similarity']}) {inc['title']}\n"
                f"  Root cause: {inc['root_cause']}\n"
                f"  Resolution: {inc['resolution']}"
                for inc in similar_incidents
            ]
        )
    else:
        similar_text = "No similar incidents found."

    # Format logs (just first 10)
    if logs:
        logs_text = "\n".join(
            [
                f"- [{log.get('level', 'INFO')}] {log.get('message', '')[:100]}"
                for log in logs[:10]
            ]
        )
    else:
        logs_text = "No error logs."

    # Create the analysis prompt
    prompt = f"""You are a Senior Site Reliability Engineer analyzing a production incident.

## Alert Information
- Service: {alert.get('service', 'unknown')}
- Alert: {alert.get('alertname', 'unknown')}
- Severity: {alert.get('severity', 'unknown')}
- Message: {alert.get('message', 'No message')}

## Current Metrics
- CPU Usage: {metrics.get('cpu_usage_percent', 'N/A')}%
- Memory Usage: {metrics.get('memory_usage_percent', 'N/A')}%
- Error Rate: {metrics.get('error_rate_percent', 'N/A')}%
- Request Rate: {metrics.get('request_rate_per_second', 'N/A')}/s
- P99 Latency: {metrics.get('latency_p99_seconds', 'N/A')}s

## Pod Status
- Total Pods: {pod_status.get('total', 'N/A')}
- Running: {pod_status.get('running', 'N/A')}
- Failed: {pod_status.get('failed', 'N/A')}

## Detected Patterns
{patterns_text}

## Recent Error Logs
{logs_text}

## Similar Past Incidents
{similar_text}

## Your Task
Analyze this incident and provide:

1. **Root Cause**: What is the most likely root cause? Be specific.

2. **Confidence**: How confident are you? (0-100%)

3. **Evidence**: List 3-5 key pieces of evidence supporting your diagnosis.

4. **Reasoning**: Explain your reasoning step by step.

Please be concise but thorough. Focus on actionable insights."""

    # Initialize GPT-4o
    llm = ChatOpenAI(
        model=MODEL,
        temperature=0,
        max_tokens=1500,
        api_key=OPENAI_API_KEY,
    )

    # Call the LLM
    response = await llm.ainvoke(
        [
            SystemMessage(
                content="You are an expert SRE analyzing production incidents. Be precise and actionable."
            ),
            HumanMessage(content=prompt),
        ]
    )

    # Parse response
    analysis = response.content

    # Extract confidence (find percentage in text)
    confidence = 0.75  # Default
    if "confidence" in analysis.lower():
        match = re.search(r"(\d{1,3})%", analysis)
        if match:
            confidence = int(match.group(1)) / 100
            confidence = min(1.0, max(0.0, confidence))  # Clamp to [0, 1]

    # Extract evidence (lines starting with - or * or numbers)
    evidence = []
    for line in analysis.split("\n"):
        line = line.strip()
        if (
            line.startswith(("-", "*", "•"))
            or re.match(r"^\d+\.", line)
        ) and len(line) > 10:
            cleaned = re.sub(r"^[-*•\d.]+\s*", "", line)
            if cleaned and len(cleaned) > 5:
                evidence.append(cleaned)
    evidence = evidence[:5]  # Max 5 evidence points

    # Extract root cause
    root_cause = _extract_root_cause(analysis)

    return {
        "root_cause": root_cause,
        "confidence": confidence,
        "evidence": evidence if evidence else ["Analysis based on detected patterns"],
        "analysis_reasoning": analysis,
    }


def _extract_root_cause(analysis: str) -> str:
    """
    Extract root cause from LLM analysis text.

    Args:
        analysis: Full LLM response text

    Returns:
        Extracted root cause string
    """
    root_cause = "Unable to determine root cause"

    # Try to find text after "Root Cause" header
    if "root cause" in analysis.lower():
        # Split on "root cause" (case insensitive)
        parts = re.split(r"root\s*cause", analysis, flags=re.IGNORECASE)
        if len(parts) > 1:
            after_root_cause = parts[1][:500]
            # Clean up - remove markdown headers, colons, etc.
            cleaned = re.sub(r"^[:\s*#]+", "", after_root_cause).strip()
            # Get first meaningful line/sentence
            lines = [l.strip() for l in cleaned.split("\n") if l.strip()]
            if lines:
                first_line = lines[0]
                # Remove leading markdown/bullets
                first_line = re.sub(r"^[-*•\d.]+\s*", "", first_line)
                if first_line and len(first_line) > 10:
                    root_cause = first_line[:200]

    return root_cause
