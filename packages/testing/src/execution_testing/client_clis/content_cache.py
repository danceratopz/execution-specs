"""Cross-fork t8n content cache for deduplicating equivalent t8n calls."""

import hashlib
import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Set

from .cli_types import TransitionToolOutput

logger = logging.getLogger(__name__)


@dataclass
class CodeState:
    """Git tree hashes for cache invalidation."""

    forks: Dict[str, str] = field(default_factory=dict)
    shared: str = ""
    test_dirs: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def compute(cls, repo_root: Path) -> "CodeState":
        """Compute current code state from git tree hashes."""
        forks: Dict[str, str] = {}
        test_dirs: Dict[str, str] = {}

        # Get fork tree hashes
        forks_dir = repo_root / "src" / "ethereum" / "forks"
        if forks_dir.exists():
            for fork_dir in sorted(forks_dir.iterdir()):
                if fork_dir.is_dir() and not fork_dir.name.startswith(
                    ("_", ".")
                ):
                    tree_hash = _git_tree_hash(
                        repo_root,
                        f"src/ethereum/forks/{fork_dir.name}/",
                    )
                    if tree_hash:
                        forks[fork_dir.name] = tree_hash

        # Get shared module hashes (crypto + utils)
        shared_parts = []
        for module in ("crypto", "utils"):
            h = _git_tree_hash(
                repo_root, f"src/ethereum/{module}/"
            )
            if h:
                shared_parts.append(h)
        shared = hashlib.sha256(
            "".join(shared_parts).encode()
        ).hexdigest()[:16]

        # Get test directory hashes (EIP-level dirs)
        tests_dir = repo_root / "tests"
        if tests_dir.exists():
            for fork_test_dir in sorted(tests_dir.iterdir()):
                if (
                    fork_test_dir.is_dir()
                    and not fork_test_dir.name.startswith(("_", "."))
                ):
                    for eip_dir in sorted(fork_test_dir.iterdir()):
                        if (
                            eip_dir.is_dir()
                            and not eip_dir.name.startswith(("_", "."))
                        ):
                            rel_path = (
                                f"tests/{fork_test_dir.name}/{eip_dir.name}/"
                            )
                            tree_hash = _git_tree_hash(
                                repo_root, rel_path
                            )
                            if tree_hash:
                                test_dirs[rel_path] = tree_hash

        return cls(forks=forks, shared=shared, test_dirs=test_dirs)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for JSON storage."""
        return {
            "forks": self.forks,
            "shared": self.shared,
            "test_dirs": self.test_dirs,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodeState":
        """Deserialize from dict."""
        return cls(
            forks=data.get("forks", {}),
            shared=data.get("shared", ""),
            test_dirs=data.get("test_dirs", {}),
        )


def _git_tree_hash(repo_root: Path, path: str) -> str | None:
    """Get git tree hash for a path relative to repo root."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", f"HEAD:{path}"],
            capture_output=True,
            text=True,
            cwd=repo_root,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def _find_repo_root() -> Path | None:
    """Find the git repository root."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


@dataclass
class EquivalenceGroup:
    """A group of forks that produce identical t8n output."""

    output_hash: str
    forks: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict."""
        return {
            "output_hash": self.output_hash,
            "forks": self.forks,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EquivalenceGroup":
        """Deserialize from dict."""
        return cls(
            output_hash=data["output_hash"],
            forks=data["forks"],
        )


@dataclass
class ContentCacheManifest:
    """Persistent cache manifest for cross-fork t8n equivalence."""

    MANIFEST_VERSION = 1

    code_state: CodeState = field(default_factory=CodeState)
    equivalences: Dict[str, EquivalenceGroup] = field(
        default_factory=dict
    )
    _invalidated_forks: Set[str] = field(
        default_factory=set, repr=False
    )
    _invalidated_test_dirs: Set[str] = field(
        default_factory=set, repr=False
    )
    _recording: Dict[str, Dict[str, str]] = field(
        default_factory=dict, repr=False
    )

    @classmethod
    def load(
        cls, path: Path, current_code_state: CodeState
    ) -> "ContentCacheManifest":
        """Load manifest and validate against current code state.

        Return empty manifest if file missing or shared code changed.
        """
        if not path.exists():
            logger.info("No content cache manifest found at %s", path)
            return cls(code_state=current_code_state)

        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(
                "Failed to read content cache manifest: %s", e
            )
            return cls(code_state=current_code_state)

        if data.get("version") != cls.MANIFEST_VERSION:
            logger.info(
                "Content cache manifest version mismatch, ignoring"
            )
            return cls(code_state=current_code_state)

        stored_state = CodeState.from_dict(data.get("code_state", {}))

        # If shared code changed, invalidate everything
        if stored_state.shared != current_code_state.shared:
            logger.info(
                "Shared code changed, invalidating entire content cache"
            )
            return cls(code_state=current_code_state)

        # Load equivalences
        equivalences: Dict[str, EquivalenceGroup] = {}
        for key, group_data in data.get("equivalences", {}).items():
            equivalences[key] = EquivalenceGroup.from_dict(group_data)

        manifest = cls(
            code_state=current_code_state,
            equivalences=equivalences,
        )

        # Determine which forks have changed
        for fork_name, current_hash in current_code_state.forks.items():
            stored_hash = stored_state.forks.get(fork_name)
            if stored_hash != current_hash:
                manifest._invalidated_forks.add(fork_name)
                logger.info(
                    "Fork '%s' code changed, removing from "
                    "equivalence groups",
                    fork_name,
                )

        # Determine which test dirs have changed
        for dir_path, current_hash in (
            current_code_state.test_dirs.items()
        ):
            stored_hash = stored_state.test_dirs.get(dir_path)
            if stored_hash != current_hash:
                manifest._invalidated_test_dirs.add(dir_path)
                logger.info(
                    "Test dir '%s' changed, removing affected "
                    "equivalences",
                    dir_path,
                )

        # Remove invalidated forks from equivalence groups
        if manifest._invalidated_forks:
            for group in manifest.equivalences.values():
                group.forks = [
                    f
                    for f in group.forks
                    if f not in manifest._invalidated_forks
                ]

        return manifest

    def are_equivalent(
        self,
        content_key: str,
        fork_a: str,
        fork_b: str,
        test_path: str | None = None,
    ) -> bool:
        """Check if two forks produce identical output for a content key.

        Return False if either fork was invalidated or if the test
        directory changed.
        """
        if content_key not in self.equivalences:
            return False

        # Check test dir invalidation
        if test_path and self._is_test_dir_invalidated(test_path):
            return False

        group = self.equivalences[content_key]
        return fork_a in group.forks and fork_b in group.forks

    def _is_test_dir_invalidated(self, test_path: str) -> bool:
        """Check if the test's EIP directory was invalidated."""
        for inv_dir in self._invalidated_test_dirs:
            if test_path.startswith(inv_dir):
                return True
        return False

    def record(
        self,
        content_key: str,
        fork: str,
        output_hash: str,
    ) -> None:
        """Record a t8n result during manifest generation."""
        if content_key not in self._recording:
            self._recording[content_key] = {}
        self._recording[content_key][fork] = output_hash

    def build_equivalences_from_recording(self) -> None:
        """Build equivalence groups from recorded results."""
        self.equivalences.clear()
        for content_key, fork_hashes in self._recording.items():
            # Group forks by output hash
            hash_to_forks: Dict[str, List[str]] = {}
            for fork, out_hash in fork_hashes.items():
                hash_to_forks.setdefault(out_hash, []).append(fork)

            # Keep the largest group (most reuse potential)
            best_hash = ""
            best_forks: List[str] = []
            for out_hash, forks in hash_to_forks.items():
                if len(forks) > len(best_forks):
                    best_hash = out_hash
                    best_forks = forks

            if len(best_forks) >= 2:
                self.equivalences[content_key] = EquivalenceGroup(
                    output_hash=best_hash,
                    forks=sorted(best_forks),
                )

    def save(self, path: Path) -> None:
        """Write manifest to disk."""
        self.build_equivalences_from_recording()

        data: Dict[str, Any] = {
            "version": self.MANIFEST_VERSION,
            "code_state": self.code_state.to_dict(),
            "equivalences": {
                key: group.to_dict()
                for key, group in self.equivalences.items()
            },
        }

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n"
        )
        logger.info(
            "Saved content cache manifest: %d equivalence groups",
            len(self.equivalences),
        )

    @property
    def has_equivalences(self) -> bool:
        """Return True if the manifest has any equivalence groups."""
        return len(self.equivalences) > 0


@dataclass(kw_only=True)
class ContentCacheStats:
    """Stats for cross-fork content cache."""

    hits: int = 0
    misses: int = 0
    equivalence_groups: int = 0

    def to_dict(self) -> Dict[str, int]:
        """Convert to dict for xdist transfer."""
        return {
            "content_cache_hits": self.hits,
            "content_cache_misses": self.misses,
            "content_cache_equiv_groups": self.equivalence_groups,
        }

    def add(self, other: "ContentCacheStats") -> None:
        """Add another stats object to this one."""
        self.hits += other.hits
        self.misses += other.misses
        self.equivalence_groups += other.equivalence_groups

    @classmethod
    def from_dict(
        cls, data: Dict[str, int]
    ) -> "ContentCacheStats":
        """Create from dict (xdist transfer)."""
        return cls(
            hits=data.get("content_cache_hits", 0),
            misses=data.get("content_cache_misses", 0),
            equivalence_groups=data.get(
                "content_cache_equiv_groups", 0
            ),
        )
