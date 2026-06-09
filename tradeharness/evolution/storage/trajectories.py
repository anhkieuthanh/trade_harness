from __future__ import annotations

import json
import os
from typing import Any


def append_episode_record(path: str, episode: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(episode) + "\n")


def load_trajectory_episodes(path: str) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        return []

    episodes: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                episodes.append(payload)
    return episodes
