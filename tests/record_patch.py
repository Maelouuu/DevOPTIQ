#!/usr/bin/env python3
"""
Helper CLI pour enregistrer un patch dans tests/patches.json.
Usage :
    python tests/record_patch.py --json '{"patch_uid": "...", ...}'
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PATCHES_FILE = Path(__file__).parent / "patches.json"


def load_patches():
    if not PATCHES_FILE.exists():
        return []
    try:
        return json.loads(PATCHES_FILE.read_text())
    except json.JSONDecodeError:
        return []


def save_patches(patches):
    PATCHES_FILE.write_text(json.dumps(patches, indent=2, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", required=True, help="Patch object as JSON string")
    args = parser.parse_args()

    try:
        patch = json.loads(args.json)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    required = {"patch_uid", "title", "node_ids", "page_slug",
                "failure_reason", "was_real_bug", "root_cause",
                "error", "fix_description", "files_changed", "author"}
    missing = required - patch.keys()
    if missing:
        print(f"❌ Missing fields: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    patches = load_patches()
    existing_uids = {p["patch_uid"] for p in patches}
    if patch["patch_uid"] in existing_uids:
        print(f"⚠️  patch_uid '{patch['patch_uid']}' already exists — skipped.", file=sys.stderr)
        sys.exit(0)

    patch.setdefault("fixed_at", datetime.now(timezone.utc).isoformat())
    patches.append(patch)
    save_patches(patches)
    print(f"✅ Patch '{patch['patch_uid']}' recorded ({len(patches)} total).")


if __name__ == "__main__":
    main()
