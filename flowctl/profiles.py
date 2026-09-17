from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


PROFILE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")

DEFAULT_DELIVERABLE_KEYS = (
    "plans",
    "reports",
    "ci_reports",
    "evidence",
    "runs",
    "state",
)


@dataclass(frozen=True)
class ProfileContext:
    profile_id: str
    write_roots: dict[str, Path]
    default_roots: dict[str, Path]
    read_roots: dict[str, list[Path]]

    @property
    def active(self) -> bool:
        return bool(self.profile_id)


def default_deliverable_roots(root: Path) -> dict[str, Path]:
    flow_root = root / ".flow"
    return {
        "plans": flow_root / "plans",
        "reports": flow_root / "reports",
        "ci_reports": flow_root / "reports" / "ci",
        "evidence": flow_root / "reports" / "evidence",
        "runs": flow_root / "runs",
        "state": flow_root / "state",
    }


def _workspace_relative(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def _require_relative_under(root: Path, raw: object, *, label: str, parent: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"`{label}` must be a non-empty workspace-relative path.")
    candidate = Path(raw.strip())
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"`{label}` must be workspace-relative and cannot contain `..`.")
    path = root / candidate
    relative = _workspace_relative(root, path)
    if relative != parent and not relative.startswith(parent.rstrip("/") + "/"):
        raise ValueError(f"`{label}` must be under `{parent}`.")
    return path


def load_profile(root: Path, profile_id: str) -> dict[str, object]:
    normalized = profile_id.strip()
    if not PROFILE_ID_RE.match(normalized):
        raise ValueError(f"Invalid profile id `{profile_id}`.")
    path = root / "profiles" / f"{normalized}.json"
    if not path.is_file():
        raise ValueError(f"Profile `{normalized}` not found at `{path.relative_to(root)}`.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Profile `{normalized}` is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Profile `{normalized}` must be a JSON object.")
    validate_profile(root, payload, expected_id=normalized)
    return payload


def load_profiles(root: Path) -> list[dict[str, object]]:
    profile_root = root / "profiles"
    if not profile_root.exists():
        return []
    profiles: list[dict[str, object]] = []
    for path in sorted(profile_root.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                validate_profile(root, payload)
                profiles.append(payload)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
    return profiles


def validate_profile(root: Path, payload: Mapping[str, object], *, expected_id: str | None = None) -> None:
    profile_id = str(payload.get("id", "") or "").strip()
    if not PROFILE_ID_RE.match(profile_id):
        raise ValueError("`id` must be a non-empty lowercase slug.")
    if expected_id is not None and profile_id != expected_id:
        raise ValueError(f"Profile id `{profile_id}` does not match requested id `{expected_id}`.")

    spec_roots = payload.get("spec_roots")
    if not isinstance(spec_roots, list) or not spec_roots:
        raise ValueError("`spec_roots` must be a non-empty list.")
    for index, raw in enumerate(spec_roots, start=1):
        _require_relative_under(root, raw, label=f"spec_roots[{index}]", parent="specs")

    deliverables = payload.get("deliverables")
    if not isinstance(deliverables, dict):
        raise ValueError("`deliverables` must be an object.")
    for key, raw in deliverables.items():
        _require_relative_under(root, raw, label=f"deliverables.{key}", parent=".flow")


def profile_matches_spec(root: Path, profile: Mapping[str, object], spec_path: Path) -> bool:
    spec_relative = _workspace_relative(root, spec_path)
    for raw_root in profile.get("spec_roots", []):
        if not isinstance(raw_root, str):
            continue
        normalized = raw_root.strip().strip("/")
        if spec_relative == normalized or spec_relative.startswith(normalized + "/"):
            return True
    return False


def resolve_profile_context(
    *,
    root: Path,
    spec_path: Path | None,
    explicit_profile: str | None,
    default_roots: Mapping[str, Path] | None = None,
) -> ProfileContext:
    defaults = {
        key: Path(value)
        for key, value in (default_roots or default_deliverable_roots(root)).items()
    }
    profile: Mapping[str, object] | None = None
    profile_id = ""
    explicit = str(explicit_profile or "").strip()
    if explicit:
        profile = load_profile(root, explicit)
        profile_id = str(profile["id"])
    elif spec_path is not None:
        matches = [
            candidate
            for candidate in load_profiles(root)
            if profile_matches_spec(root, candidate, spec_path)
        ]
        if len(matches) > 1:
            ids = ", ".join(str(item.get("id", "")) for item in matches)
            raise ValueError(f"Spec matches multiple profiles ({ids}); pass `--profile` explicitly.")
        if matches:
            profile = matches[0]
            profile_id = str(profile["id"])

    write_roots = dict(defaults)
    if profile is not None:
        deliverables = profile.get("deliverables", {})
        if isinstance(deliverables, dict):
            for key, raw in deliverables.items():
                if key in write_roots and isinstance(raw, str):
                    write_roots[key] = root / raw

    read_roots: dict[str, list[Path]] = {}
    for key, default_root in defaults.items():
        candidates = [write_roots[key], default_root] if profile is not None else [default_root]
        read_roots[key] = _unique_paths(candidates)
    return ProfileContext(
        profile_id=profile_id,
        write_roots=write_roots,
        default_roots=defaults,
        read_roots=read_roots,
    )


def artifact_candidates(roots: list[Path], filename: str) -> list[Path]:
    return _unique_paths([root / filename for root in roots])


def first_existing_path(candidates: list[Path]) -> Path:
    for path in candidates:
        if path.exists():
            return path
    if not candidates:
        raise ValueError("At least one artifact candidate is required.")
    return candidates[0]
