from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parent
    src_root = project_root / "src"
    sys.path.insert(0, str(src_root))

    from palworld_trainer.app import main as app_main

    return app_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
