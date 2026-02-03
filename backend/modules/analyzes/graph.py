from langgraph.graph import StateGraph, START, END

from backend.modules.analyzes.state import AnalyzerState
from backend.modules.analyzes.nodes.analyze_patterns import detect_patterns_node
from backend.modules.analyzes.nodes.similar_issues import search_similar_node
from backend.modules.analyzes.nodes.llm_analyze import llm_analyze_node
from backend.modules.analyzes.nodes.actions_ask import generate_actions_node


def build_analyzer_subgraph() -> StateGraph:
    """
    Build and compile the Analyzer subgraph.

    Flow:
        START -> detect_patterns -> search_similar -> llm_analyze -> generate_actions -> END

    Returns:
        Compiled StateGraph for the Analyzer agent.
    """
    graph = StateGraph(AnalyzerState)

    # Add nodes
    graph.add_node("detect_patterns", detect_patterns_node)
    graph.add_node("search_similar", search_similar_node)
    graph.add_node("llm_analyze", llm_analyze_node)
    graph.add_node("generate_actions", generate_actions_node)

    # Add edges (sequential flow)
    graph.add_edge(START, "detect_patterns")
    graph.add_edge("detect_patterns", "search_similar")
    graph.add_edge("search_similar", "llm_analyze")
    graph.add_edge("llm_analyze", "generate_actions")
    graph.add_edge("generate_actions", END)

    return graph.compile()


# Create the subgraph singleton
analyzer_subgraph = build_analyzer_subgraph()
