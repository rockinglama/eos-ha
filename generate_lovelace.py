#!/usr/bin/env python3
"""Generate .storage/lovelace.eos from dashboards/eos-energy.yaml."""
import json
import yaml
import sys

with open("dashboards/eos-energy.yaml") as f:
    dashboard = yaml.safe_load(f)

storage = {
    "version": 1,
    "minor_version": 1,
    "key": "lovelace.eos",
    "data": {
        "config": dashboard
    }
}

output = json.dumps(storage, indent=2, ensure_ascii=False)
print(output)

if len(sys.argv) > 1:
    with open(sys.argv[1], "w") as f:
        f.write(output)
    print(f"Written to {sys.argv[1]}", file=sys.stderr)
