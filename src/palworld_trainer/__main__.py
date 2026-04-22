"""Console entry point for the packaged exe and ``python -m palworld_trainer``."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _smoke_test() -> int:
    """Quick exit used by the build pipeline to verify the exe at least starts."""
    marker_path = os.environ.get("PALWORLD_TRAINER_SMOKE_TEST_FILE")
    if marker_path:
        Path(marker_path).write_text("smoke-ok", encoding="utf-8")
    return 0


def main() -> int:
    if "--smoke-test" in sys.argv or os.environ.get("PALWORLD_TRAINER_SMOKE_TEST") == "1":
        return _smoke_test()
    if "--chat-helper" in sys.argv or os.environ.get("PALWORLD_TRAINER_CHAT_HELPER_PAYLOAD"):
        from palworld_trainer.game_control import run_chat_helper_from_env

        return run_chat_helper_from_env()

    from palworld_trainer.app import run

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
