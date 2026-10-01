"""
Drift Detector - Agent Quality Monitoring

An observer agent that monitors another agent's responses over time,
detecting quality degradation, inconsistencies, or behavioral drift.
Demonstrates monitoring AI systems with AI.

Prerequisites:
    pip install -r requirements.txt

Learning objectives:
- Understand how to monitor agent behavior over time
- See how observer agents detect quality drift
- Learn to build feedback loops for agent oversight
- Practice AI-monitoring-AI patterns
"""

import time
import random
from shared.model import get_model
from shared.input_utils import get_multiline_input
from shared.streaming import StreamingCallbackHandler
from strands import Agent, tool


# --- Simulated Agent Responses (the system being observed) ---

class SimulatedAgent:
    """Simulates an agent whose quality degrades over time."""

    def __init__(self):
        self.call_count = 0
        self.drift_threshold = random.randint(5, 8)  # When drift starts

    def respond(self, query: str) -> dict:
        """Generate a response with potential quality drift."""
        self.call_count += 1

        # Before drift: high quality responses
        if self.call_count < self.drift_threshold:
            return {
                "query": query,
                "response": self._good_response(query),
                "latency_ms": random.randint(80, 200),
                "tokens_used": random.randint(100, 300),
                "call_number": self.call_count,
            }
        # After drift: degraded responses
        else:
            return {
                "query": query,
                "response": self._degraded_response(query),
                "latency_ms": random.randint(500, 3000),  # Slower
                "tokens_used": random.randint(500, 1500),  # More verbose
                "call_number": self.call_count,
            }

    def _good_response(self, query: str) -> str:
        good_responses = [
            f"Based on the query '{query[:30]}...', here is a concise and accurate answer with relevant details.",
            f"The answer to '{query[:30]}...' is straightforward: [clear, factual response with sources].",
            f"Regarding '{query[:30]}...': [well-structured response with key points and actionable advice].",
        ]
        return random.choice(good_responses)

    def _degraded_response(self, query: str) -> str:
        degraded_responses = [
            f"Um, regarding '{query[:30]}...' I think maybe the answer could be something like... well it depends on many factors and there are various perspectives to consider and honestly it's quite complex...",
            f"I'm not entirely sure about '{query[:30]}...' but here's what I think might be relevant although I could be wrong and you should probably verify this elsewhere...",
            f"'{query[:30]}...' - this is a great question! Let me think... actually there are so many angles to this. On one hand... but on the other hand... it's really hard to say definitively...",
            f"ERROR: I apologize but I seem to be having difficulty processing this request. The query '{query[:30]}...' is... let me try again... [repeats itself]",
        ]
        return random.choice(degraded_responses)


simulated_agent = SimulatedAgent()
observations = []


# --- Observer Tools ---

@tool
def observe_agent_response(query: str) -> str:
    """Send a query to the monitored agent and observe its response.

    Args:
        query: The query to send to the agent being monitored
    """
    result = simulated_agent.respond(query)
    observations.append(result)

    print(f"      📡 Observed call #{result['call_number']}: "
          f"latency={result['latency_ms']}ms, tokens={result['tokens_used']}")
    print(f"         Response preview: \"{result['response'][:80]}...\"")

    return (
        f"OBSERVATION #{result['call_number']}:\n"
        f"  Query: {result['query']}\n"
        f"  Response: {result['response']}\n"
        f"  Latency: {result['latency_ms']}ms\n"
        f"  Tokens used: {result['tokens_used']}"
    )


@tool
def get_observation_metrics() -> str:
    """Get aggregate metrics from all observations so far.

    Returns latency trends, token usage trends, and response quality indicators.
    """
    if not observations:
        return "No observations recorded yet."

    latencies = [o["latency_ms"] for o in observations]
    tokens = [o["tokens_used"] for o in observations]

    # Calculate trends
    mid = len(observations) // 2
    if mid > 0:
        early_latency = sum(latencies[:mid]) / mid
        late_latency = sum(latencies[mid:]) / (len(latencies) - mid)
        early_tokens = sum(tokens[:mid]) / mid
        late_tokens = sum(tokens[mid:]) / (len(tokens) - mid)
    else:
        early_latency = late_latency = sum(latencies) / len(latencies)
        early_tokens = late_tokens = sum(tokens) / len(tokens)

    metrics = (
        f"OBSERVATION METRICS ({len(observations)} total calls):\n"
        f"  Latency — early avg: {early_latency:.0f}ms, recent avg: {late_latency:.0f}ms\n"
        f"  Tokens  — early avg: {early_tokens:.0f}, recent avg: {late_tokens:.0f}\n"
        f"  Latency range: {min(latencies)}ms - {max(latencies)}ms\n"
        f"  Token range: {min(tokens)} - {max(tokens)}"
    )
    print(f"      📊 Metrics: avg latency {sum(latencies)/len(latencies):.0f}ms, "
          f"avg tokens {sum(tokens)/len(tokens):.0f}")
    return metrics


@tool
def flag_drift(drift_type: str, evidence: str, recommendation: str) -> str:
    """Flag a detected drift issue with evidence and recommendation.

    Args:
        drift_type: Type of drift (latency, quality, verbosity, consistency)
        evidence: Specific evidence supporting the drift detection
        recommendation: Suggested action to address the drift
    """
    print(f"      🚨 DRIFT DETECTED: {drift_type}")
    print(f"         Evidence: {evidence[:80]}")
    print(f"         Action: {recommendation[:80]}")

    return f"Drift flagged: [{drift_type}] {evidence} → Recommendation: {recommendation}"


SYSTEM_PROMPT = """You are a Drift Detection Agent that analyzes an agent's performance metrics over time.

IMPORTANT CONTEXT: In production, you do NOT send test queries to the monitored agent.
Instead, you analyze traces and metrics that are already being collected via OpenTelemetry
from real user traffic. The observability data (latency, token counts, response quality)
already exists — you just analyze it periodically or when a threshold triggers.

For this lab exercise, we simulate this by having you send test queries to observe
responses directly. In production, you would pull aggregated metrics from CloudWatch
or trace data from S3/OpenSearch.

Your role is PASSIVE — you observe, measure, and report. You do NOT fix the monitored agent.

Monitoring workflow:
1. Gather observations (in this lab: send test queries; in production: pull traces)
2. After collecting data, check metrics using get_observation_metrics for trends
3. Look for signs of drift:
   - Increasing latency (response time growing over time)
   - Increasing verbosity (token count growing without better answers)
   - Quality degradation (vague, uncertain, or repetitive responses)
   - Inconsistency (similar queries getting very different quality)
4. If drift is detected, flag it using flag_drift with specific evidence

The goal is to detect WHEN an agent starts degrading — not to fix it.
Provide specific evidence so the team knows what to investigate."""


def main():
    """Run the drift detector agent."""
    print("Drift Detector - Agent Quality Monitor")
    print("=" * 40)
    print("This observer analyzes an agent's performance over time to detect")
    print("quality degradation, latency spikes, and behavioral drift.")
    print()
    print("NOTE: In production, this agent analyzes traces/metrics already")
    print("collected via OpenTelemetry — NOT by sending additional test queries.")
    print("This lab simulates the pattern by probing a simulated agent directly.")
    print("Type 'quit' to exit\n")

    print("Choose an action (pick a number, or type your own):")
    print("  1. Run a monitoring session (10 observations, analyze trends)")
    print("  2. Run an extended session (15 observations — more likely to detect drift)")
    print("  3. Review current metrics only\n")

    # Streaming handler so the user can watch the observer reason about
    # metrics alongside the tool prints (📡 📊 🚨 icons).
    stream_handler = StreamingCallbackHandler()
    agent = Agent(
        model=get_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[observe_agent_response, get_observation_metrics, flag_drift],
        callback_handler=stream_handler,
    )

    prompts = {
        "1": "Run a monitoring session. Send 10 varied test queries to the monitored agent, then analyze the metrics for any signs of drift. Flag any issues you detect.",
        "2": "Run an extended monitoring session. Send 15 varied test queries to the monitored agent, check metrics periodically, and flag any drift you detect. Be thorough.",
        "3": "Check the current observation metrics and summarize the health of the monitored agent.",
    }

    while True:
        user_input = get_multiline_input("You: ").strip()

        if user_input.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            break

        if not user_input:
            continue

        # A menu number expands to its canned prompt; anything else is sent
        # to the agent as-is so you can try your own scenarios.
        if user_input in prompts:
            user_input = prompts[user_input]

        try:
            stream_handler.reset()
            print("\nObserver: ", end="", flush=True)
            start_time = time.time()
            agent(user_input)
            elapsed = time.time() - start_time
            print(f"\n({elapsed:.1f}s)\n")
        except Exception as e:
            print(f"\nError: {e}\n")


if __name__ == "__main__":
    main()
