"""Interface de persistência consumida pelo caso de uso de transições de estado."""

from collections.abc import Sequence
from typing import Any, Protocol
from uuid import UUID


class StateTransitionStore(Protocol):
    def lock_story_state_version(self, story_id: UUID) -> int | None: ...
    def create(self, *, story_id: UUID, values: dict[str, Any]) -> Any: ...
    def get_in_story(self, story_id: UUID, transition_id: UUID) -> Any | None: ...
    def change_status(
        self,
        *,
        story_id: UUID,
        transition_id: UUID,
        expected_statuses: Sequence[str],
        values: dict[str, Any],
    ) -> bool: ...
