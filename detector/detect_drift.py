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


# Main Orchestrator
def main():
    print("=" * 60)
    print("  TerraGuard AI - Drift Detection Engine")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60)

    # Step 1: Run Terraform Plan
    exit_code, stdout, stderr = run_terraform_plan()

    if exit_code == 0:
        print("✅ No drift detected. Infrastructure matches the Terraform state.")
        sys.exit(0)

    if exit_code == 1:
        print("❌ Terraform plan errored:\n{stderr}")
        sys.exit(1)

    # exit_code == 2: DRIFT DETECTED
    print("\n⚠️ DRIFT DETECTED! Analyzing with AI...\n")

    # Step 2: Parse the plan output
    changes = parse_plan_output(stdout, stderr)
    print(f"   Resources changed: {changes['resources_changed']}")
    print(f"   Attributes changed: {changes['attributes_changed']}")


if __name__ == "__main__":
    main()
