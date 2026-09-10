#!/usr/bin/env python3
"""
Pulls the project plan and RAID log sheets from Smartsheet in a single run
and writes the combined data to a JSON file for the dashboard to consume.
Optionally also pulls a "Project Comment" sheet (Health / Comments columns)
that the PM edits directly in Smartsheet to set the overall program status
pill and post stakeholder-facing comments on the dashboard.

Requires:
    pip install smartsheet-python-sdk

Environment variables:
    SMARTSHEET_TOKEN        - Smartsheet API access token
    PROJECT_PLAN_SHEET_ID    - Sheet ID for the project plan
    RAID_LOG_SHEET_ID        - Sheet ID for the RAID log
    PROJECT_COMMENT_SHEET_ID - (optional) Sheet ID for the PM's Project Comment
                                sheet. If unset, the dashboard just falls back
                                to its auto-calculated health heuristic.
"""

import os
import sys
import json
from datetime import datetime, timezone

import smartsheet


def get_env_or_exit(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        print(f"Missing required environment variable: {name}", file=sys.stderr)
        sys.exit(1)
    return value


def sheet_to_dict(sheet) -> dict:
    """Convert a Smartsheet Sheet object into a plain dict of columns + rows."""
    columns = [col.title for col in sheet.columns]
    column_id_to_title = {col.id: col.title for col in sheet.columns}

    rows = []
    for row in sheet.rows:
        row_data = {}
        for cell in row.cells:
            title = column_id_to_title.get(cell.column_id)
            if title is None:
                continue
            # display_value handles formulas/dropdowns nicely; fall back to raw value
            row_data[title] = cell.display_value if cell.display_value is not None else cell.value
        row_data["_row_id"] = row.id
        rows.append(row_data)

    return {
        "sheet_name": sheet.name,
        "columns": columns,
        "rows": rows,
    }


def main():
    token = get_env_or_exit("SMARTSHEET_TOKEN")
    plan_sheet_id = get_env_or_exit("PROJECT_PLAN_SHEET_ID")
    raid_sheet_id = get_env_or_exit("RAID_LOG_SHEET_ID")

    client = smartsheet.Smartsheet(token)
    client.errors_as_exceptions(True)

    print("Fetching project plan sheet...")
    plan_sheet = client.Sheets.get_sheet(plan_sheet_id)

    print("Fetching RAID log sheet...")
    raid_sheet = client.Sheets.get_sheet(raid_sheet_id)

    combined = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_plan": sheet_to_dict(plan_sheet),
        "raid_log": sheet_to_dict(raid_sheet),
    }

    # Project Comment sheet is optional so this script keeps working before
    # the secret is configured — the dashboard just falls back to its
    # auto-calculated health heuristic and shows no PM comments.
    comment_sheet_id = os.environ.get("PROJECT_COMMENT_SHEET_ID")
    if comment_sheet_id:
        print("Fetching project comment sheet...")
        comment_sheet = client.Sheets.get_sheet(comment_sheet_id)
        combined["project_comment"] = sheet_to_dict(comment_sheet)
    else:
        print("PROJECT_COMMENT_SHEET_ID not set — skipping project comment sheet.")

    output_path = os.environ.get("OUTPUT_PATH", "data/dashboard-data.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(combined, f, indent=2, default=str)

    print(f"Wrote combined data to {output_path}")
    print(f"  Project plan rows: {len(combined['project_plan']['rows'])}")
    print(f"  RAID log rows: {len(combined['raid_log']['rows'])}")
    if "project_comment" in combined:
        print(f"  Project comment rows: {len(combined['project_comment']['rows'])}")


if __name__ == "__main__":
    main()
