#!/usr/bin/env python3
"""
TerraGuard AI - Drift Detection Engine
Runs terraform plan, parses drift, sends to Groq for AI analysis,
then routes alerts based on risk score
"""

from dotenv import load_dotenv

load_dotenv()

import os
import sys
import json
import subprocess
import re
import requests
from datetime import datetime, timezone

# Configuration
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"  # Free, fast, excellent

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "")

INFRA_DIR = os.path.join(os.path.dirname(__file__), "..", "infra")


# Terraform Plan
def run_terraform_plan() -> tuple[int, str, str]:
    """
    Runs terraform plan -detailed-exitcode
    Exit codes:
        0 = No changes (no drift)
        1 = Error
        2 = Changes present (DRIFT DETECTED)
    Returns: (exit_code, stdout, stderr)
    """
    print("🔍 Running terraform plan...")

    # First, ensure we have the latest state
    init_result = subprocess.run(
        ["terraform", "init", "-reconfigure", "-input=false"],
        capture_output=True,
        text=True,
        cwd=INFRA_DIR,
    )
    if init_result.returncode != 0:
        print(f"❌ terraform init failed:\n{init_result.stderr}")
        sys.exit(1)

    # Run plan with JSON output for easier parsing
    result = subprocess.run(
        [
            "terraform",
            "plan",
            "-detailed-exitcode",
            "-no-color",
            "-input=false",
            "-out=tfplan",
        ],
        capture_output=True,
        text=True,
        cwd=INFRA_DIR,
        env={
            **os.environ,
            "TF_VAR_db_password": os.environ.get("TF_VAR_db_password", "placeholder"),
        },
    )

    return result.returncode, result.stdout, result.stderr


def parse_plan_output(stdout: str, stderr: str) -> dict:
    """
    Extracts meaningful drift information from terraform plan output.
    Strips secrets and focuses on resource changes.
    """
    changes = {
        "resources_changed": [],
        "resources_added": [],
        "resources_destroyed": [],
        "raw_summary": "",
    }

    # Extract changed resource blocks
    resource_pattern = re.compile(
        r"#\s+([\w.]+)\s+will\s+be\s+(updated|replaced|destroyed|created)", re.MULTILINE
    )
    for match in resource_pattern.finditer(stdout):
        resource_name, action = match.group(1), match.group(2)
        if action == "updated":
            changes["resources_changed"].append(resource_name)
        elif action in ("replaced", "created"):
            changes["resources_added"].append(resource_name)
        elif action == "destroyed":
            changes["resources_destroyed"].append(resource_name)

    # Extract the plan summary line
    summary_match = re.search(r"Plan:.*?(?:\n|$)", stdout)
    if summary_match:
        changes["raw_summary"] = summary_match.group(0).strip()

    # Extract attribute changes (sanitized — strip values, keep attribute names)
    attr_changes = []
    attr_pattern = re.compile(r"^\s+[~+-]\s+(\w+)\s+=", re.MULTILINE)
    for match in attr_pattern.finditer(stdout):
        attr_name = match.group(1)
        # Skip sensitive attributes
        if attr_name.lower() not in (
            "password",
            "secret",
            "key",
            "token",
            "credential",
        ):
            attr_changes.append(attr_name)

    changes["attributes_changed"] = list(set(attr_changes))

    return changes


# AI Analysis (Groq)
def analyze_with_groq(plan_summary: str, changes: dict) -> dict:
    """
    Sends drift information to Groq (Llama 3.3) for risk analysis.
    Returns a structured risk assessment with remediation advice.
    """
    print("🤖 Sending to Groq AI for analysis...")

    prompt = f"""You are a Senior Cloud Security Engineer reviewing a Terraform drift report.
Drift means someone manually changed AWS infrastructure OUTSIDE of Terraform, which is a security and compliance risk.

DRIFT DETECTED:
Resources Modified: {json.dumps(changes.get("resources_changed", []))}
Resources Added: {json.dumps(changes.get("resources_added", []))}
Resources Destroyed: {json.dumps(changes.get("resources_destroyed", []))}
Attributes Changed: {json.dumps(changes.get("attributes_changed", []))}
Plan Summary: {plan_summary}

Respond ONLY with a valid JSON object (no markdown, no explanation outside JSON):
{{
  "risk_level": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
  "risk_score": 1-10,
  "category": "Security|Compliance|Configuration|Cost|Unknown",
  "summary": "One sentence: what changed and why it matters",
  "impact": "What could go wrong if this drift is not addressed",
  "action": "REVERT|ADOPT|INVESTIGATE|MONITOR",
  "remediation": "Exact command or HCL snippet to fix this (terraform import, terraform apply, etc.)",
  "reasoning": "Why you assigned this risk level"
}}

Risk Level Guide:
- CRITICAL: Security group opened to 0.0.0.0/0, IAM role with * permissions, encryption disabled
- HIGH: Public S3 bucket, database made publicly accessible, logging disabled  
- MEDIUM: Instance type changed, scaling limits modified, tag removed
- LOW: Description updated, non-security tag added
- INFO: No meaningful risk (e.g., auto-assigned resource ID changed)"""

    try:
        response = requests.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,  # Low temp for consistent, factual analysis
                "max_tokens": 1000,
            },
            timeout=30,
        )
        response.raise_for_status()

        content = response.json()["choices"][0]["message"]["content"].strip()

        # Clean up any accidental markdown fences
        content = re.sub(r"^```(?:json)?\n?", "", content)
        content = re.sub(r"\n?```$", "", content)

        return json.loads(content)

    except json.JSONDecodeError as e:
        print(f"⚠️ Could not parse AI response as JSON: {e}")
        return {
            "risk_level": "MEDIUM",
            "risk_score": 5,
            "category": "Unknown",
            "summary": "Drift detected but AI analysis failed to parse",
            "impact": "Unknown — manual review required",
            "action": "INVESTIGATE",
            "remediation": "Run: terraform plan -detailed-exitcode",
            "reasoning": "AI parse error",
        }
    except Exception as e:
        print(f"⚠️ Groq API error: {e}")
        raise


# Alerting
RISK_EMOJI = {
    "CRITICAL": "🚨",
    "HIGH": "🔴",
    "MEDIUM": "🟡",
    "LOW": "🟢",
    "INFO": "ℹ️",
}


def send_slack_alert(analysis: dict, changes: dict):
    """Sends a rich Slack alert for HIGH/CRITICAL drift."""
    if not SLACK_WEBHOOK_URL:
        print("⚠️ No Slack webhook configured, skipping Slack alert")
        return

    risk = analysis.get("risk_level", "UNKNOWN")
    emoji = RISK_EMOJI.get(risk, "⚠️")

    payload = {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} TerraGuard AI — {risk} Drift Detected",
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Risk Score:*\n{analysis.get('risk_score')}/10",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Category:*\n{analysis.get('category')}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Action Required:*\n`{analysis.get('action')}`",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Resources Affected:*\n{len(changes.get('resources_changed', []))} changed",
                    },
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*AI Analysis:*\n{analysis.get('summary')}",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Impact:*\n{analysis.get('impact')}",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Remediation:*\n```{analysis.get('remediation')}```",
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Detected at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')} | Repo: {GITHUB_REPO}",
                    }
                ],
            },
        ]
    }

    response = requests.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
    if response.status_code == 200:
        print("✅ Slack alert sent successfully")
    else:
        print(f"❌ Slack alert failed: {response.status_code} {response.text}")


def create_github_issue(analysis: dict, changes: dict):
    """Creates a GitHub Issue for LOW/MEDIUM/INFO drift."""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        print("⚠️ No GitHub token/repo configured, skipping issue creation")
        return

    risk = analysis.get("risk_level", "UNKNOWN")
    title = f"[TerraGuard AI] {risk} Drift: {analysis.get('summary', 'Infrastructure drift detected')}"

    body = f"""## 🔍 TerraGuard AI Drift Report

**Detected:** {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}

### Risk Assessment
| Field | Value |
|-------|-------|
| Risk Level | **{risk}** |
| Risk Score | {analysis.get("risk_score")}/10 |
| Category | {analysis.get("category")} |
| Recommended Action | `{analysis.get("action")}` |

### Summary
{analysis.get("summary")}

### Impact
{analysis.get("impact")}

### Resources Affected
- **Modified:** {", ".join(changes.get("resources_changed", ["none"])) or "none"}
- **Added:** {", ".join(changes.get("resources_added", ["none"])) or "none"}
- **Destroyed:** {", ".join(changes.get("resources_destroyed", ["none"])) or "none"}

### AI Remediation Advice
```bash
{analysis.get("remediation")}
```

### AI Reasoning
{analysis.get("reasoning")}

---
*Generated by [TerraGuard AI](https://github.com/{GITHUB_REPO}) using Llama 3.3 via Groq*
"""

    response = requests.post(
        f"https://api.github.com/repos/{GITHUB_REPO}/issues",
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
        },
        json={
            "title": title,
            "body": body,
            "labels": ["drift-detected", f"risk-{risk.lower()}"],
        },
        timeout=15,
    )

    if response.status_code == 201:
        issue_url = response.json().get("html_url")
        print(f"✅ GitHub Issue created: {issue_url}")
    else:
        print(f"❌ GitHub Issue creation failed: {response.status_code}")


# Main Orchestrator
def main():
    print("=" * 60)
    print("  TerraGuard AI — Drift Detection Engine")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)

    # Step 1: Run Terraform Plan
    exit_code, stdout, stderr = run_terraform_plan()

    if exit_code == 0:
        print("✅ No drift detected. Infrastructure matches Terraform state.")
        sys.exit(0)

    if exit_code == 1:
        print(f"❌ Terraform plan errored:\n{stderr}")
        sys.exit(1)

    # exit_code == 2: DRIFT DETECTED
    print(f"\n⚠️  DRIFT DETECTED! Analyzing with AI...\n")

    # Step 2: Parse the plan output
    changes = parse_plan_output(stdout, stderr)
    print(f"   Resources changed: {changes['resources_changed']}")
    print(f"   Attributes changed: {changes['attributes_changed']}")

    # Step 3: AI Analysis via Groq
    plan_text = stdout[-3000:] if len(stdout) > 3000 else stdout  # Limit context size
    analysis = analyze_with_groq(plan_text, changes)

    print(f"\n📊 AI Risk Assessment:")
    print(f"   Risk Level:  {analysis.get('risk_level')}")
    print(f"   Risk Score:  {analysis.get('risk_score')}/10")
    print(f"   Category:    {analysis.get('category')}")
    print(f"   Summary:     {analysis.get('summary')}")
    print(f"   Action:      {analysis.get('action')}")
    print(f"   Remediation: {analysis.get('remediation')}")

    # Step 4: Route alert based on risk level
    risk_level = analysis.get("risk_level", "MEDIUM")

    if risk_level in ("CRITICAL", "HIGH"):
        print(f"\n🚨 {risk_level} risk — sending Slack alert immediately!")
        send_slack_alert(analysis, changes)
        create_github_issue(analysis, changes)  # Also create an issue for tracking

    elif risk_level in ("MEDIUM", "LOW", "INFO"):
        print(f"\n📝 {risk_level} risk — creating GitHub Issue for backlog")
        create_github_issue(analysis, changes)

    print("\n✅ TerraGuard AI drift detection complete.")

    # Exit with code 2 to signal drift was found (useful for CI/CD checks)
    sys.exit(2)


if __name__ == "__main__":
    main()
