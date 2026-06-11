"""uproot-only ROOT-format event reading."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .paths import expand_input_paths


@dataclass(frozen=True)
class Event:
    event_id: int
    px: np.ndarray
    py: np.ndarray
    pz: np.ndarray
    energy: np.ndarray
    weight: float = 1.0


class UprootEventSource:
    """Yield events grouped by event id using uproot arrays.

    This class intentionally uses no PyROOT or ROOT native APIs.
    """

    def __init__(
        self,
        files: list[str],
        tree: str = "tracks",
        branches: dict[str, str] | None = None,
        batch_entries: int = 250_000,
        max_events: int | None = None,
    ):
        self.files = expand_input_paths(files)
        self.tree = tree
        self.branches = branches or {
            "event_id": "eventID",
            "px": "px",
            "py": "py",
            "pz": "pz",
            "energy": "energy",
        }
        self.batch_entries = int(batch_entries)
        self.max_events = max_events

    def __iter__(self) -> Iterator[Event]:
        try:
            import uproot
        except ImportError as exc:
            raise RuntimeError("uproot is required for ROOT-format input I/O") from exc

        branch_names = [
            self.branches["event_id"],
            self.branches["px"],
            self.branches["py"],
            self.branches["pz"],
            self.branches["energy"],
        ]
        yielded = 0
        pending: dict[str, Any] | None = None

        for path in self.files:
            with uproot.open(path) as root_file:
                tree = root_file[self.tree]
                for batch in tree.iterate(branch_names, step_size=self.batch_entries, library="np"):
                    normalized = {
                        "event_id": batch[self.branches["event_id"]],
                        "px": batch[self.branches["px"]],
                        "py": batch[self.branches["py"]],
                        "pz": batch[self.branches["pz"]],
                        "energy": batch[self.branches["energy"]],
                    }
                    events, pending = _events_from_batch(normalized, pending)
                    for event in events:
                        yield event
                        yielded += 1
                        if self.max_events is not None and yielded >= self.max_events:
                            return
                if pending is not None:
                    yield _pending_to_event(pending)
                    yielded += 1
                    pending = None
                    if self.max_events is not None and yielded >= self.max_events:
                        return


def _events_from_batch(batch: dict[str, np.ndarray], pending: dict[str, Any] | None) -> tuple[list[Event], dict[str, Any] | None]:
    event_ids = np.asarray(batch["event_id"])
    events: list[Event] = []
    if event_ids.size == 0:
        return events, pending

    starts = np.r_[0, np.nonzero(event_ids[1:] != event_ids[:-1])[0] + 1]
    stops = np.r_[starts[1:], event_ids.size]

    for start, stop in zip(starts, stops):
        chunk = {k: np.asarray(v[start:stop]) for k, v in batch.items()}
        eid = int(chunk["event_id"][0])
        if pending is not None and int(pending["event_id"]) == eid:
            for key in ("px", "py", "pz", "energy"):
                pending[key].append(chunk[key])
        else:
            if pending is not None:
                events.append(_pending_to_event(pending))
            pending = {"event_id": eid, "px": [chunk["px"]], "py": [chunk["py"]], "pz": [chunk["pz"]], "energy": [chunk["energy"]]}
    return events, pending


def _pending_to_event(pending: dict[str, Any]) -> Event:
    return Event(
        event_id=int(pending["event_id"]),
        px=np.concatenate(pending["px"]),
        py=np.concatenate(pending["py"]),
        pz=np.concatenate(pending["pz"]),
        energy=np.concatenate(pending["energy"]),
        weight=1.0,
    )
