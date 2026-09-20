from __future__ import annotations

import json
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.biomass_phase1 import RAW_DIR, run_biomass_phase1


def main():
    raw_root = Path(sys.argv[1]) if len(sys.argv) > 1 else RAW_DIR
    result = run_biomass_phase1(raw_root)
    print(
        json.dumps(
            {
                "status": "ok",
                "total_records": len(result["records"]),
                "missing_capacity": result["quality_report"]["count_missing_capacity"],
                "possible_duplicates": result["quality_report"]["count_possible_duplicates"],
                "validation_sources_found": result["quality_report"]["validation_sources_found"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
