import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.generators import get_generators_quality_report


def main():
    print(json.dumps(get_generators_quality_report(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
