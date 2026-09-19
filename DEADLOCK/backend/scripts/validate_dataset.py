#!/usr/bin/env python3
"""
DEADLOCK Dataset Validator
Validates JSON syntax, schema compliance, ID uniqueness, referential integrity,
date logical consistency, scenario references, and expected results evidence.
"""

import json
import os
import sys
from datetime import datetime

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT_DIR, "data")
SCENARIOS_DIR = os.path.join(DATA_DIR, "scenarios")

SEEDED_PROJECT_PATH = os.path.join(DATA_DIR, "seeded_project.json")
EXPECTED_RESULTS_PATH = os.path.join(DATA_DIR, "expected_results.json")
SCENARIO_FILES = [
    os.path.join(SCENARIOS_DIR, "deadline_failure.json"),
    os.path.join(SCENARIOS_DIR, "developer_bottleneck.json"),
    os.path.join(SCENARIOS_DIR, "false_positive.json"),
]

REQUIRED_TOP_LEVEL = [
    "project",
    "developers",
    "milestones",
    "issues",
    "pull_requests",
    "commits",
    "reviews",
    "dependencies",
    "deployments",
    "deadlines"
]

def parse_iso_date(date_str):
    if not date_str:
        return None
    try:
        # Normalize Z to +00:00 for ISO parsing
        if date_str.endswith("Z"):
            date_str = date_str[:-1] + "+00:00"
        return datetime.fromisoformat(date_str)
    except Exception:
        return None

def validate():
    results = {
        "json_syntax": "PASS",
        "references": "PASS",
        "dependencies": "PASS",
        "dates": "PASS",
        "scenarios": "PASS",
        "overall": "PASS"
    }

    errors = []
    all_known_ids = set()
    dev_ids = set()
    milestone_ids = set()
    issue_ids = set()
    pr_ids = set()
    commit_ids = set()
    deployment_ids = set()
    deadline_ids = set()

    # --- Step 1: JSON Syntax & Top-level Check ---
    print("[1/6] Checking JSON syntax and structure...")
    
    # Check seeded_project.json
    if not os.path.exists(SEEDED_PROJECT_PATH):
        errors.append(f"Missing file: {SEEDED_PROJECT_PATH}")
        results["json_syntax"] = "FAIL"
    else:
        try:
            with open(SEEDED_PROJECT_PATH, "r", encoding="utf-8") as f:
                seeded_data = json.load(f)
            
            for key in REQUIRED_TOP_LEVEL:
                if key not in seeded_data:
                    errors.append(f"seeded_project.json missing required top-level section: '{key}'")
                    results["json_syntax"] = "FAIL"
        except Exception as e:
            errors.append(f"Invalid JSON in seeded_project.json: {e}")
            results["json_syntax"] = "FAIL"

    # Check expected_results.json
    if not os.path.exists(EXPECTED_RESULTS_PATH):
        errors.append(f"Missing file: {EXPECTED_RESULTS_PATH}")
        results["json_syntax"] = "FAIL"
    else:
        try:
            with open(EXPECTED_RESULTS_PATH, "r", encoding="utf-8") as f:
                expected_data = json.load(f)
        except Exception as e:
            errors.append(f"Invalid JSON in expected_results.json: {e}")
            results["json_syntax"] = "FAIL"

    # Check scenarios
    scenario_datas = {}
    for s_path in SCENARIO_FILES:
        if not os.path.exists(s_path):
            errors.append(f"Missing scenario file: {s_path}")
            results["scenarios"] = "FAIL"
        else:
            try:
                with open(s_path, "r", encoding="utf-8") as f:
                    scenario_datas[s_path] = json.load(f)
            except Exception as e:
                errors.append(f"Invalid JSON in scenario file {s_path}: {e}")
                results["scenarios"] = "FAIL"

    if results["json_syntax"] == "FAIL":
        results["overall"] = "FAIL"
        print_report(results, errors)
        return False

    # --- Step 2: Extract and Validate Unique IDs ---
    print("[2/6] Validating ID uniqueness across entities...")
    
    # Project ID
    proj_id = seeded_data.get("project", {}).get("id")
    if proj_id:
        all_known_ids.add(proj_id)

    # Developers
    for dev in seeded_data.get("developers", []):
        did = dev.get("id")
        if not did:
            errors.append("Developer object missing 'id'")
        elif did in all_known_ids:
            errors.append(f"Duplicate ID found: {did}")
        else:
            all_known_ids.add(did)
            dev_ids.add(did)

    # Milestones
    for ms in seeded_data.get("milestones", []):
        mid = ms.get("id")
        if not mid:
            errors.append("Milestone object missing 'id'")
        elif mid in all_known_ids:
            errors.append(f"Duplicate ID found: {mid}")
        else:
            all_known_ids.add(mid)
            milestone_ids.add(mid)

    # Issues
    for issue in seeded_data.get("issues", []):
        iid = issue.get("id")
        if not iid:
            errors.append("Issue object missing 'id'")
        elif iid in all_known_ids:
            errors.append(f"Duplicate ID found: {iid}")
        else:
            all_known_ids.add(iid)
            issue_ids.add(iid)

    # Pull Requests
    for pr in seeded_data.get("pull_requests", []):
        prid = pr.get("id")
        if not prid:
            errors.append("PR object missing 'id'")
        elif prid in all_known_ids:
            errors.append(f"Duplicate ID found: {prid}")
        else:
            all_known_ids.add(prid)
            pr_ids.add(prid)

    # Commits
    for c in seeded_data.get("commits", []):
        cid = c.get("id")
        if not cid:
            errors.append("Commit object missing 'id'")
        elif cid in all_known_ids:
            errors.append(f"Duplicate ID found: {cid}")
        else:
            all_known_ids.add(cid)
            commit_ids.add(cid)

    # Reviews
    for rev in seeded_data.get("reviews", []):
        rid = rev.get("id")
        if not rid:
            errors.append("Review object missing 'id'")
        elif rid in all_known_ids:
            errors.append(f"Duplicate ID found: {rid}")
        else:
            all_known_ids.add(rid)

    # Dependencies
    for dep in seeded_data.get("dependencies", []):
        did = dep.get("id")
        if not did:
            errors.append("Dependency object missing 'id'")
        elif did in all_known_ids:
            errors.append(f"Duplicate ID found: {did}")
        else:
            all_known_ids.add(did)

    # Deployments
    for dep in seeded_data.get("deployments", []):
        dpid = dep.get("id")
        if not dpid:
            errors.append("Deployment object missing 'id'")
        elif dpid in all_known_ids:
            errors.append(f"Duplicate ID found: {dpid}")
        else:
            all_known_ids.add(dpid)
            deployment_ids.add(dpid)

    # Deadlines
    for dl in seeded_data.get("deadlines", []):
        dlid = dl.get("id")
        if not dlid:
            errors.append("Deadline object missing 'id'")
        elif dlid in all_known_ids:
            errors.append(f"Duplicate ID found: {dlid}")
        else:
            all_known_ids.add(dlid)
            deadline_ids.add(dlid)

    if len(errors) > 0:
        results["references"] = "FAIL"

    # --- Step 3: Referencial Integrity Checks ---
    print("[3/6] Validating entity references (developers, issues, PRs, milestones)...")

    # Check issues
    for issue in seeded_data.get("issues", []):
        reporter = issue.get("reporter_id")
        assignee = issue.get("assignee_id")
        milestone = issue.get("milestone_id")
        
        if reporter and reporter not in dev_ids:
            errors.append(f"Issue {issue['id']} references unknown reporter_id: {reporter}")
            results["references"] = "FAIL"
        if assignee and assignee not in dev_ids:
            errors.append(f"Issue {issue['id']} references unknown assignee_id: {assignee}")
            results["references"] = "FAIL"
        if milestone and milestone not in milestone_ids:
            errors.append(f"Issue {issue['id']} references unknown milestone_id: {milestone}")
            results["references"] = "FAIL"

    # Check PRs
    for pr in seeded_data.get("pull_requests", []):
        author = pr.get("author_id")
        if author and author not in dev_ids:
            errors.append(f"PR {pr['id']} references unknown author_id: {author}")
            results["references"] = "FAIL"
        for reviewer in pr.get("reviewers", []):
            if reviewer not in dev_ids:
                errors.append(f"PR {pr['id']} references unknown reviewer: {reviewer}")
                results["references"] = "FAIL"
        for linked_issue in pr.get("linked_issues", []):
            if linked_issue not in issue_ids:
                errors.append(f"PR {pr['id']} references unknown linked_issue: {linked_issue}")
                results["references"] = "FAIL"

    # Check Commits
    for c in seeded_data.get("commits", []):
        author = c.get("author_id")
        if author and author not in dev_ids:
            errors.append(f"Commit {c['id']} references unknown author_id: {author}")
            results["references"] = "FAIL"
        pr_ref = c.get("pr_id")
        if pr_ref and pr_ref not in pr_ids:
            errors.append(f"Commit {c['id']} references unknown pr_id: {pr_ref}")
            results["references"] = "FAIL"

    # Check Reviews
    for rev in seeded_data.get("reviews", []):
        reviewer = rev.get("reviewer_id")
        pr_ref = rev.get("pr_id")
        if reviewer and reviewer not in dev_ids:
            errors.append(f"Review {rev['id']} references unknown reviewer_id: {reviewer}")
            results["references"] = "FAIL"
        if pr_ref and pr_ref not in pr_ids:
            errors.append(f"Review {rev['id']} references unknown pr_id: {pr_ref}")
            results["references"] = "FAIL"

    # Check Deployments
    for dep in seeded_data.get("deployments", []):
        for issue_ref in dep.get("related_issues", []):
            if issue_ref not in issue_ids:
                errors.append(f"Deployment {dep['id']} references unknown issue: {issue_ref}")
                results["references"] = "FAIL"
        for pr_ref in dep.get("related_prs", []):
            if pr_ref not in pr_ids:
                errors.append(f"Deployment {dep['id']} references unknown PR: {pr_ref}")
                results["references"] = "FAIL"

    # Check Deadlines
    for dl in seeded_data.get("deadlines", []):
        ms_ref = dl.get("milestone_id")
        if ms_ref and ms_ref not in milestone_ids:
            errors.append(f"Deadline {dl['id']} references unknown milestone_id: {ms_ref}")
            results["references"] = "FAIL"

    # --- Step 4: Dependency Graph Checks ---
    print("[4/6] Validating dependencies graph references...")
    for dep_rel in seeded_data.get("dependencies", []):
        source = dep_rel.get("source_id")
        target = dep_rel.get("target_id")
        if not source or source not in all_known_ids:
            errors.append(f"Dependency {dep_rel.get('id')} has invalid source_id: {source}")
            results["dependencies"] = "FAIL"
        if not target or target not in all_known_ids:
            errors.append(f"Dependency {dep_rel.get('id')} has invalid target_id: {target}")
            results["dependencies"] = "FAIL"

    # --- Step 5: Date Logic Checks ---
    print("[5/6] Validating date formats and chronological order...")
    # Check all timestamp fields
    date_fields_map = [
        (seeded_data.get("milestones", []), ["created_at", "target_date"]),
        (seeded_data.get("issues", []), ["created_at", "updated_at", "closed_at"]),
        (seeded_data.get("pull_requests", []), ["created_at", "updated_at", "merged_at", "closed_at"]),
        (seeded_data.get("commits", []), ["timestamp"]),
        (seeded_data.get("reviews", []), ["submitted_at"]),
        (seeded_data.get("deployments", []), ["scheduled_at", "executed_at"]),
        (seeded_data.get("deadlines", []), ["due_date"]),
    ]

    for item_list, fields in date_fields_map:
        for item in item_list:
            item_id = item.get("id", "unknown")
            created_dt = parse_iso_date(item.get("created_at"))
            
            for field in fields:
                val = item.get(field)
                if val:
                    dt = parse_iso_date(val)
                    if dt is None:
                        errors.append(f"Entity {item_id} has invalid ISO date in '{field}': '{val}'")
                        results["dates"] = "FAIL"
            
            # Sequence check: created_at <= updated_at / closed_at / merged_at
            if created_dt:
                for lat_field in ["updated_at", "closed_at", "merged_at"]:
                    if lat_field in item and item[lat_field]:
                        lat_dt = parse_iso_date(item[lat_field])
                        if lat_dt and lat_dt < created_dt:
                            errors.append(f"Entity {item_id} has {lat_field} ({item[lat_field]}) before created_at ({item['created_at']})")
                            results["dates"] = "FAIL"

    # --- Step 6: Scenarios & Expected Results Integrity ---
    print("[6/6] Validating scenarios & expected_results evidence references...")
    
    # Check expected_results evidence references
    for risk in expected_data.get("hidden_risks", []):
        rid = risk.get("risk_id")
        for ev_id in risk.get("evidence_ids", []):
            if ev_id not in all_known_ids:
                errors.append(f"Expected risk '{rid}' references unknown evidence_id: {ev_id}")
                results["scenarios"] = "FAIL"
        for dep_id in risk.get("dependency_chain", []):
            if dep_id not in all_known_ids:
                errors.append(f"Expected risk '{rid}' references unknown item in dependency_chain: {dep_id}")
                results["scenarios"] = "FAIL"
        for aff_id in risk.get("affected_items", []):
            if aff_id not in all_known_ids:
                errors.append(f"Expected risk '{rid}' references unknown item in affected_items: {aff_id}")
                results["scenarios"] = "FAIL"

    # Check false positive evidence
    fp = expected_data.get("false_positive", {})
    if fp:
        for ev_id in fp.get("evidence_ids_safe", []):
            if ev_id not in all_known_ids:
                errors.append(f"False positive references unknown evidence_id_safe: {ev_id}")
                results["scenarios"] = "FAIL"

    # Check focused scenario files
    for s_path, s_data in scenario_datas.items():
        s_filename = os.path.basename(s_path)
        for ref_id in s_data.get("scenario_evidence_ids", []):
            if ref_id not in all_known_ids:
                errors.append(f"Scenario {s_filename} references unknown scenario_evidence_id: {ref_id}")
                results["scenarios"] = "FAIL"

    # Overall outcome
    if any(v == "FAIL" for v in results.values()):
        results["overall"] = "FAIL"

    print_report(results, errors)
    return results["overall"] == "PASS"

def print_report(results, errors):
    print("\n================ DATASET VALIDATION REPORT ================")
    print(f"JSON Syntax Check:          {results['json_syntax']}")
    print(f"Entity References Check:    {results['references']}")
    print(f"Dependencies Graph Check:   {results['dependencies']}")
    print(f"Date Consistency Check:     {results['dates']}")
    print(f"Scenario & Evidence Check:  {results['scenarios']}")
    print("-----------------------------------------------------------")
    print(f"OVERALL STATUS:             {results['overall']}")
    print("===========================================================")

    if errors:
        print(f"\nFound {len(errors)} error(s):")
        for idx, err in enumerate(errors, 1):
            print(f"  {idx}. {err}")
        print()

if __name__ == "__main__":
    success = validate()
    sys.exit(0 if success else 1)
