from __future__ import annotations

import os
import sys
from pathlib import Path


if "--smoke-test" in sys.argv or os.environ.get("PALWORLD_TRAINER_SMOKE_TEST") == "1":
    marker_path = os.environ.get("PALWORLD_TRAINER_SMOKE_TEST_FILE")
    if marker_path:
        Path(marker_path).write_text("smoke-ok", encoding="utf-8")
    raise SystemExit(0)

from palworld_trainer.app import main


if __name__ == "__main__":
    raise SystemExit(main())
