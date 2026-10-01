"""
Log Analyzer - Anomaly Detection in Application Logs

An observer agent that ingests application logs, detects anomalies,
classifies severity, and generates alerts. Demonstrates the core
observer pattern: ingest → parse → reason → classify → log.

Prerequisites:
    pip install -r requirements.txt

Learning objectives:
- Understand passive observation and anomaly detection
- See how LLMs reason about unstructured log data
- Learn to classify events by severity using AI
- Practice building alert pipelines from raw telemetry
"""

import time
import random
from datetime import datetime, timedelta
from shared.model import get_model
from shared.input_utils import get_multiline_input
from shared.streaming import StreamingCallbackHandler
from strands import Agent, tool


# --- Simulated Log Stream ---

class LogStream:
    """Generates realistic application logs with occasional anomalies."""

    LOG_TEMPLATES = {
        "normal": [
            "INFO  [web-server] Request completed: GET /api/users (200) 45ms",
            "INFO  [web-server] Request completed: POST /api/orders (201) 120ms",
            "INFO  [auth-service] User login successful: user_id=u-{id}",
            "INFO  [db-pool] Connection acquired in 3ms (pool: 8/20 active)",
            "DEBUG [cache] Cache hit for key: session:{id}",
            "INFO  [scheduler] Job 'cleanup_temp' completed in 230ms",
            "INFO  [web-server] Health check passed: all services healthy",
        ],
        "warning": [
            "WARN  [db-pool] Connection pool at 85% capacity (17/20 active)",
            "WARN  [web-server] Request slow: GET /api/reports (200) 2340ms",
            "WARN  [auth-service] Failed login attempt #3 for user_id=u-{id}",
            "WARN  [cache] Cache miss rate elevated: 34% (threshold: 20%)",
            "WARN  [disk] Disk usage at 78% on /var/data",
        ],
        "error": [
            "ERROR [web-server] Request failed: POST /api/payments (500) timeout after 30000ms",
            "ERROR [db-pool] Connection pool exhausted! 20/20 active, 5 waiting",
            "ERROR [auth-service] Authentication service unreachable: connection refused",
            "ERROR [web-server] Unhandled exception: NullPointerException in OrderService.process()",
            "ERROR [memory] OOM killer invoked: process 'data-processor' using 3.8GB (limit: 4GB)",
        ],
        "critical": [
            "CRITICAL [web-server] All worker threads exhausted — incoming requests being dropped",
            "CRITICAL [db-pool] Database primary node unreachable for 45s — failover initiated",
            "CRITICAL [security] Unusual access pattern: 500 requests/sec from IP 192.168.1.{id}",
            "CRITICAL [disk] Disk usage at 97% on /var/data — writes may fail",
        ],
    }

    def generate_batch(self, count: int = 20, anomaly_rate: float = 0.3) -> list:
        """Generate a batch of log entries with some anomalies."""
        logs = []
        base_time = datetime.now() - timedelta(minutes=count)

        for i in range(count):
            timestamp = (base_time + timedelta(seconds=i * 3)).strftime("%Y-%m-%d %H:%M:%S")
            rand = random.random()

            if rand < (1 - anomaly_rate):
                template = random.choice(self.LOG_TEMPLATES["normal"])
            elif rand < (1 - anomaly_rate * 0.4):
                template = random.choice(self.LOG_TEMPLATES["warning"])
            elif rand < (1 - anomaly_rate * 0.1):
                template = random.choice(self.LOG_TEMPLATES["error"])
            else:
                template = random.choice(self.LOG_TEMPLATES["critical"])

            entry = f"[{timestamp}] {template.format(id=random.randint(1000, 9999))}"
            logs.append(entry)

        return logs


log_stream = LogStream()
analysis_history = []


# --- Observer Tools ---

@tool
def ingest_logs(count: int = 20) -> str:
    """Ingest a batch of application logs from the monitoring stream.

    Args:
        count: Number of log entries to ingest (default: 20)
    """
    logs = log_stream.generate_batch(count=count)
    log_text = "\n".join(logs)
    print(f"      📥 Ingested {len(logs)} log entries")
    return f"LOG BATCH ({len(logs)} entries):\n{log_text}"


@tool
def classify_alert(severity: str, summary: str, affected_service: str) -> str:
    """Classify and record an alert based on observed anomalies.

    Args:
        severity: Alert severity (info, warning, error, critical)
        summary: Brief description of the anomaly detected
        affected_service: The service or component affected
    """
    alert = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "severity": severity.upper(),
        "summary": summary,
        "service": affected_service,
    }
    analysis_history.append(alert)

    icons = {"INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌", "CRITICAL": "🚨"}
    icon = icons.get(severity.upper(), "📋")
    print(f"      {icon} [{severity.upper()}] {affected_service}: {summary}")

    return f"Alert recorded: [{severity.upper()}] {summary}"


@tool
def get_alert_history() -> str:
    """Review all alerts generated in this monitoring session.

    Returns a summary of all classified alerts.
    """
    if not analysis_history:
        return "No alerts recorded yet."

    lines = ["ALERT HISTORY:"]
    for alert in analysis_history:
        lines.append(f"  [{alert['severity']}] {alert['service']}: {alert['summary']}")
    return "\n".join(lines)


SYSTEM_PROMPT = """You are an Observer Agent that analyzes application logs after an anomaly has been detected.

IMPORTANT CONTEXT: You are NOT monitoring logs line-by-line. Traditional monitoring
(CloudWatch Alarms, threshold rules) has already detected something unusual and
triggered you. Your job is to analyze the batch of logs around the anomaly window,
correlate signals across services, identify the root cause, and produce a structured
incident report.

Your role is PASSIVE — you observe, analyze, and report. You do NOT fix issues.

When analyzing logs:
1. Ingest the batch of logs from the anomaly window using ingest_logs
2. Parse the entries — identify timestamps, severity levels, services, and patterns
3. Reason about what you observe:
   - What triggered the upstream alert?
   - Are multiple services affected? Is this a cascading failure?
   - What is the likely root cause?
   - Are there security concerns?
4. Classify each finding using classify_alert with appropriate severity
5. Provide a structured incident summary ready for the on-call team

Severity guidelines:
- INFO: Notable but not concerning (e.g., elevated cache misses)
- WARNING: Degraded performance or approaching limits
- ERROR: Service failures affecting users
- CRITICAL: System-wide impact or security threats

Think like an on-call engineer: correlate signals, identify causation (not just
correlation), and produce an actionable report."""


def main():
    """Run the log analyzer agent."""
    print("Log Analyzer - Anomaly Investigation Agent")
    print("=" * 40)
    print("This observer agent is triggered AFTER traditional monitoring")
    print("(CloudWatch Alarms, threshold rules) detects an anomaly.")
    print("It analyzes a batch of logs around the alert window to identify")
    print("root cause and produce a structured incident report.")
    print()
    print("NOTE: In production, this agent is NOT called per log line.")
    print("It receives a batch of logs after an upstream alert fires.")
    print("Type 'quit' to exit\n")

    print("Simulated alert triggers (pick a number, or type your own):")
    print("  1. Alert: Error rate exceeded 5% threshold (analyze recent logs)")
    print("  2. Alert: Multiple service degradation detected (larger window)")
    print("  3. Review incident history from this session\n")

    # Streaming handler so the user can watch the observer reason about
    # the log batch alongside the tool prints (📥 ℹ️ ⚠️ ❌ 🚨 icons).
    stream_handler = StreamingCallbackHandler()
    agent = Agent(
        model=get_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[ingest_logs, classify_alert, get_alert_history],
        callback_handler=stream_handler,
    )

    prompts = {
        "1": "UPSTREAM ALERT: CloudWatch detected error rate > 5% in the last 10 minutes. Analyze the 20 most recent log entries from the anomaly window. Identify the root cause, determine which services are affected, classify the severity, and produce an incident summary for the on-call team.",
        "2": "UPSTREAM ALERT: Multiple services showing degraded performance. Error rate elevated AND latency spikes detected across 3 services in the last 15 minutes. Analyze 30 log entries from the alert window (use count=30). Correlate the failures, identify the cascade origin, and produce a full incident report.",
        "3": "Review the full alert history and produce a summary of all incidents analyzed in this session. Note any patterns across incidents.",
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
