"""
Compliance Monitor - Policy Violation Detection

An observer agent that watches a stream of user actions and flags
policy violations. Demonstrates compliance monitoring where the
agent reasons about whether actions conform to defined rules.

Note on regulated data:
    This is a simulation that uses synthetic data. The sample policies and
    violation templates reference regulated data categories (SSN, payment
    card, bank account, salary) only to demonstrate detection logic. If you
    adapt this pattern to handle real PII, PHI, or payment card data,
    additional controls apply -- for example PCI DSS (payment cards), GDPR
    (EU personal data), and HIPAA (health information) -- and meeting those
    requirements is your responsibility. See https://aws.amazon.com/compliance/.

Prerequisites:
    pip install -r requirements.txt

Learning objectives:
- Understand compliance monitoring with LLM reasoning
- See how observer agents enforce policies without blocking actions
- Learn to detect violations in unstructured activity streams
- Practice building audit trails from observed behavior
"""

import time
import random
from datetime import datetime, timedelta
from shared.model import get_model
from shared.input_utils import get_multiline_input
from shared.streaming import StreamingCallbackHandler
from strands import Agent, tool


# --- Simulated Activity Stream ---

class ActivityStream:
    """Generates user activity events, some of which violate policies."""

    POLICIES = """
    COMPANY POLICIES:
    1. Data Access: Users may only access data for their own department
    2. Working Hours: System access outside 6AM-10PM requires manager approval
    3. Bulk Operations: Exports of more than 1000 records require audit justification
    4. Sensitive Data: PII fields (SSN, credit card) must not be included in exports
    5. Account Security: More than 5 failed login attempts triggers account lockout
    6. Data Retention: Deleting records older than 7 years requires compliance approval
    """

    NORMAL_ACTIONS = [
        {"user": "alice@example.com", "dept": "engineering", "action": "viewed", "resource": "engineering/project-roadmap.pdf", "time_offset": 0},
        {"user": "bob@example.com", "dept": "sales", "action": "exported", "resource": "sales/q3-pipeline.csv", "records": 45, "time_offset": 0},
        {"user": "carol@example.com", "dept": "hr", "action": "updated", "resource": "hr/employee-benefits.docx", "time_offset": 0},
        {"user": "dave@example.com", "dept": "finance", "action": "viewed", "resource": "finance/budget-2025.xlsx", "time_offset": 0},
        {"user": "eve@example.com", "dept": "engineering", "action": "deployed", "resource": "engineering/api-v2.3", "time_offset": 0},
        {"user": "frank@example.com", "dept": "sales", "action": "viewed", "resource": "sales/customer-list.csv", "time_offset": 0},
    ]

    VIOLATIONS = [
        {"user": "bob@example.com", "dept": "sales", "action": "accessed", "resource": "hr/salary-data.csv", "violation": "cross-department access", "time_offset": 0},
        {"user": "alice@example.com", "dept": "engineering", "action": "exported", "resource": "engineering/user-database.csv", "records": 5200, "violation": "bulk export without justification", "time_offset": 0},
        {"user": "dave@example.com", "dept": "finance", "action": "exported", "resource": "finance/payroll.csv", "fields": "name,ssn,salary,bank_account", "violation": "PII in export (SSN)", "time_offset": 0},
        {"user": "carol@example.com", "dept": "hr", "action": "login_failed", "resource": "system", "attempts": 7, "violation": "exceeded failed login threshold", "time_offset": 0},
        {"user": "eve@example.com", "dept": "engineering", "action": "deleted", "resource": "engineering/logs-2015.tar.gz", "age_years": 10, "violation": "deleting old records without approval", "time_offset": 0},
        {"user": "frank@example.com", "dept": "sales", "action": "accessed", "resource": "sales/crm-dashboard", "violation": "after-hours access (2:30 AM)", "time_offset": -18},
    ]

    def generate_batch(self, count: int = 15, violation_rate: float = 0.3) -> tuple:
        """Generate activity events. Returns (events_text, policy_text)."""
        events = []
        base_time = datetime.now() - timedelta(hours=2)

        for i in range(count):
            if random.random() < violation_rate:
                template = random.choice(self.VIOLATIONS).copy()
            else:
                template = random.choice(self.NORMAL_ACTIONS).copy()

            timestamp = (base_time + timedelta(minutes=i * 5 + template.get("time_offset", 0) * 60))
            template["timestamp"] = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            template.pop("time_offset", None)
            template.pop("violation", None)  # Don't reveal violations to the agent

            # Format as a log entry
            entry_parts = [f"[{template['timestamp']}]"]
            entry_parts.append(f"user={template['user']}")
            entry_parts.append(f"dept={template['dept']}")
            entry_parts.append(f"action={template['action']}")
            entry_parts.append(f"resource={template['resource']}")
            if "records" in template:
                entry_parts.append(f"records={template['records']}")
            if "fields" in template:
                entry_parts.append(f"fields={template['fields']}")
            if "attempts" in template:
                entry_parts.append(f"attempts={template['attempts']}")
            if "age_years" in template:
                entry_parts.append(f"age_years={template['age_years']}")

            events.append(" | ".join(entry_parts))

        return "\n".join(events), self.POLICIES


activity_stream = ActivityStream()
violations_found = []


# --- Observer Tools ---

@tool
def ingest_activity(count: int = 15) -> str:
    """Ingest a batch of user activity events from the monitoring stream.

    Args:
        count: Number of activity events to ingest (default: 15)
    """
    events, policies = activity_stream.generate_batch(count=count)
    print(f"      📥 Ingested {count} activity events")
    return f"COMPANY POLICIES:\n{policies}\n\nACTIVITY LOG ({count} events):\n{events}"


@tool
def flag_violation(user: str, action: str, policy_violated: str, severity: str, evidence: str) -> str:
    """Flag a policy violation detected in the activity stream.

    Args:
        user: The user who violated the policy
        action: The action that violated the policy
        policy_violated: Which policy rule was violated
        severity: Severity level (low, medium, high, critical)
        evidence: Specific evidence from the activity log
    """
    violation = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user": user,
        "action": action,
        "policy": policy_violated,
        "severity": severity,
        "evidence": evidence,
    }
    violations_found.append(violation)

    icons = {"LOW": "📋", "MEDIUM": "⚠️", "HIGH": "❌", "CRITICAL": "🚨"}
    icon = icons.get(severity.upper(), "📋")
    print(f"      {icon} VIOLATION: {user} — {policy_violated}")
    print(f"         Action: {action}")

    return f"Violation recorded: {user} violated '{policy_violated}' — {evidence}"


@tool
def get_violation_report() -> str:
    """Generate a summary report of all violations detected.

    Returns a formatted compliance report.
    """
    if not violations_found:
        return "No violations detected."

    lines = [f"COMPLIANCE REPORT ({len(violations_found)} violations):"]
    for v in violations_found:
        lines.append(f"  [{v['severity'].upper()}] {v['user']}: {v['policy']}")
        lines.append(f"    Evidence: {v['evidence']}")
    return "\n".join(lines)


SYSTEM_PROMPT = """You are a Compliance Monitoring Agent that watches user activity for policy violations.

Your role is PASSIVE — you observe and report. You do NOT block actions or modify behavior.

Monitoring workflow:
1. Ingest activity events using ingest_activity
2. Review the company policies provided with the activity data
3. For each event, determine if it violates any policy:
   - Cross-department data access
   - After-hours access without approval
   - Bulk exports exceeding thresholds
   - PII exposure in exports
   - Excessive failed login attempts
   - Unauthorized deletion of old records
4. Flag each violation using flag_violation with specific evidence
5. Generate a summary report using get_violation_report

Be thorough — check EVERY event against EVERY applicable policy.
Not all events are violations. Only flag clear policy breaches with evidence."""


def main():
    """Run the compliance monitor agent."""
    print("Compliance Monitor - Policy Violation Detection")
    print("=" * 40)
    print("This observer watches user activity and flags policy violations.")
    print("It reasons about whether actions conform to company rules.")
    print("Type 'quit' to exit\n")

    print("Choose an action (pick a number, or type your own):")
    print("  1. Monitor a batch of activity (15 events, some violations)")
    print("  2. Monitor a larger batch (25 events, higher violation rate)")
    print("  3. View compliance report\n")

    # Streaming handler so the user can watch the agent reason about each
    # event alongside the tool prints (📥 violation icons).
    stream_handler = StreamingCallbackHandler()
    agent = Agent(
        model=get_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[ingest_activity, flag_violation, get_violation_report],
        callback_handler=stream_handler,
    )

    prompts = {
        "1": "Ingest 15 activity events and check each one against the company policies. Flag any violations you find, then generate a compliance report.",
        "2": "Ingest 25 activity events (use count=25). This is a high-risk period — be extra thorough checking for violations. Flag everything suspicious and generate a full report.",
        "3": "Generate the compliance violation report summarizing all issues found so far.",
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
