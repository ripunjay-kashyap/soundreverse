import argparse
import os
import sys
from pathlib import Path
from typing import TypedDict

# Ensure project root is on sys.path when running as a script
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from langgraph.graph import END, StateGraph
from langchain_core.tracers.langchain import LangChainTracer

from agents.critic import critic_node
from agents.gateway import gateway_node
from agents.analyst import analyst_node
from output.generator import output_node
from schemas.producer_settings import ProducerSettings
from schemas.signal_signature import SignalSignature
from schemas.track_request import TrackRequest

load_dotenv(override=True)


# ── State ────────────────────────────────────────────────────────────────────

class GraphState(TypedDict):
    track_request:     TrackRequest | None
    signal_signature:  SignalSignature | None
    producer_settings: ProducerSettings | None
    iteration_count:   int
    confidence:        float
    critique:          str
    critique_history:  list[str]
    critic_rounds:     list[dict]   # accumulated per-iteration: {iteration, confidence, rejected, reason}
    validation_checks: list[dict]   # final round: [{name, passed, detail}, ...]
    final:             bool
    error:             str | None
    trace_url:         str | None
    stress_test:       bool         # if True, analyst deliberately overshoots kick freq on iteration 0
    # internal: used by gateway to know which track to load
    _track_id:         str


# ── Routing ──────────────────────────────────────────────────────────────────

def _route_after_critic(state: GraphState) -> str:
    if state.get("final") or state.get("error"):
        return "output"
    return "analyst"


# ── Graph assembly ───────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    graph = StateGraph(GraphState)

    graph.add_node("gateway", gateway_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("critic", critic_node)

    graph.set_entry_point("gateway")
    graph.add_edge("gateway", "analyst")
    graph.add_edge("analyst", "critic")
    graph.add_conditional_edges("critic", _route_after_critic, {
        "analyst": "analyst",
        "output": END,
    })

    return graph.compile()


# ── CLI entry point ──────────────────────────────────────────────────────────

def _capture_trace_url(tracer: LangChainTracer) -> str | None:
    try:
        if tracer.latest_run is None:
            return None
        from langsmith import Client
        client = Client()
        # share_run makes the trace publicly viewable (no login required)
        return client.share_run(tracer.latest_run.id)
    except Exception:
        return None


def run(track_id: str, stress_test: bool = False) -> dict:
    app = build_graph()

    initial_state: GraphState = {
        "_track_id": track_id,
        "track_request": None,
        "signal_signature": None,
        "producer_settings": None,
        "iteration_count": 0,
        "confidence": 0.0,
        "critique": "",
        "critique_history": [],
        "critic_rounds": [],
        "validation_checks": [],
        "final": False,
        "error": None,
        "trace_url": None,
        "stress_test": stress_test,
    }

    project = os.environ.get("LANGSMITH_PROJECT", "soundreverse-v1")
    tracer = LangChainTracer(project_name=project)

    final_state = app.invoke(initial_state, config={"callbacks": [tracer]})

    if final_state.get("error"):
        print(f"\nError: {final_state['error']}")
        return final_state

    # Trace URL is only available after invoke completes
    trace_url = _capture_trace_url(tracer)
    final_state = {**final_state, "trace_url": trace_url}

    # Generate outputs now that we have the real trace URL
    final_state = output_node(final_state)

    print(f"\nTrack:       {track_id}")
    print(f"Confidence:  {final_state['confidence']:.2f}")
    print(f"Iterations:  {final_state['iteration_count']}")
    if final_state.get("critique"):
        print(f"Critique:    {final_state['critique']}")
    print(f"Preset:      output/{track_id}_preset.json")
    if trace_url:
        print(f"Trace:       {trace_url}")

    return final_state


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SoundReverse — Producer Session Pack generator")
    parser.add_argument("--track", required=True, help="Track ID (e.g. billie_jean_mj)")
    args = parser.parse_args()
    run(args.track)
