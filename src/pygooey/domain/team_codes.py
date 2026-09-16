"""Encode and decode TFT Team Planner codes.

The client format is deliberately kept separate from catalog IDs. A planner
code is a 12-bit value assigned by Riot, while a catalog ID such as
``TFT18_Ahri`` is the stable identifier used by this project.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace


EMPTY_PLANNER_CODE = 0
MAX_PLANNER_CODE = 0xFFF


class TeamCodeError(ValueError):
    """Raised when a Team Planner code cannot be decoded or encoded."""


@dataclass(frozen=True, slots=True)
class TeamCodeFormat:
    """The versioned wire format for one set's Team Planner strings."""

    prefix: str
    set_id: str
    slot_count: int = 10

    def __post_init__(self) -> None:
        if len(self.prefix) != 2:
            raise TeamCodeError("team code prefixes must be two hexadecimal characters")
        try:
            int(self.prefix, 16)
        except ValueError as error:
            raise TeamCodeError("team code prefixes must be hexadecimal") from error
        if not self.set_id:
            raise TeamCodeError("team code set IDs cannot be empty")
        if self.slot_count < 1:
            raise TeamCodeError("team code slot counts must be positive")

    @property
    def version(self) -> int:
        return int(self.prefix, 16)


DEFAULT_TEAM_CODE_FORMAT = TeamCodeFormat("02", "TFTSet18", 10)
# Backward-compatible aliases for callers that only support the first format.
TEAM_CODE_VERSION = DEFAULT_TEAM_CODE_FORMAT.version
TEAM_CODE_PREFIX = DEFAULT_TEAM_CODE_FORMAT.prefix
TEAM_CODE_SET_ID = DEFAULT_TEAM_CODE_FORMAT.set_id
TEAM_CODE_SLOT_COUNT = DEFAULT_TEAM_CODE_FORMAT.slot_count


@dataclass(frozen=True, slots=True)
class TeamSlot:
    """One imported slot, including enough raw data to preserve ambiguity."""

    planner_code: int
    unit_id: str | None = None
    candidates: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0 <= self.planner_code <= MAX_PLANNER_CODE:
            raise TeamCodeError("planner codes must fit in 12 bits")

    @property
    def is_empty(self) -> bool:
        return self.planner_code == EMPTY_PLANNER_CODE and self.unit_id is None

    @property
    def is_ambiguous(self) -> bool:
        return len(self.candidates) > 1 and self.unit_id is None

    @property
    def is_unknown(self) -> bool:
        return (
            self.planner_code != EMPTY_PLANNER_CODE
            and self.unit_id is None
            and not self.candidates
        )


@dataclass(frozen=True, slots=True)
class DecodedTeam:
    """A ten-slot team that can be edited and encoded again."""

    code_format: TeamCodeFormat
    slots: tuple[TeamSlot, ...]
    raw_code: str

    def __post_init__(self) -> None:
        if len(self.slots) != self.code_format.slot_count:
            raise TeamCodeError(
                f"a team code must contain {self.code_format.slot_count} slots"
            )

    @property
    def version(self) -> int:
        return self.code_format.version

    @property
    def set_id(self) -> str:
        return self.code_format.set_id

    def replace_slot(
        self,
        index: int,
        unit_id: str | None,
        unit_to_planner_code: Mapping[str, int],
    ) -> DecodedTeam:
        """Return a copy with one slot changed to a catalog unit or empty."""
        if not 0 <= index < self.code_format.slot_count:
            raise IndexError(
                f"slot index must be between 0 and {self.code_format.slot_count - 1}"
            )
        if unit_id is None:
            new_slot = TeamSlot(EMPTY_PLANNER_CODE)
        else:
            try:
                planner_code = unit_to_planner_code[unit_id]
            except KeyError as error:
                raise TeamCodeError(f"unknown catalog unit: {unit_id}") from error
            new_slot = TeamSlot(planner_code, unit_id, (unit_id,))
        slots = list(self.slots)
        slots[index] = new_slot
        return replace(self, slots=tuple(slots))

    def encode(self, unit_to_planner_code: Mapping[str, int]) -> str:
        """Encode this team, preserving unresolved imported planner values."""
        return encode_team_code(self, unit_to_planner_code)


def build_reverse_planner_codes(
    unit_to_planner_code: Mapping[str, int],
) -> dict[int, tuple[str, ...]]:
    """Build the reverse lookup needed to translate planner IDs to unit IDs."""
    grouped: dict[int, list[str]] = {}
    for unit_id, planner_code in unit_to_planner_code.items():
        if not isinstance(planner_code, int) or not 0 <= planner_code <= MAX_PLANNER_CODE:
            raise TeamCodeError(f"invalid planner code for {unit_id}")
        grouped.setdefault(planner_code, []).append(unit_id)
    return {code: tuple(unit_ids) for code, unit_ids in grouped.items()}


def decode_team_code(
    code: str,
    planner_to_units: Mapping[int, Sequence[str]],
    *,
    code_format: TeamCodeFormat = DEFAULT_TEAM_CODE_FORMAT,
) -> DecodedTeam:
    """Decode a set's Team Planner string into editable slots.

    Unknown planner IDs are retained as raw slots. IDs shared by multiple
    catalog units, such as Lux's variants, are retained as candidates so an
    export can preserve the original code until the user selects a variant.
    """
    if not isinstance(code, str):
        raise TeamCodeError("team code must be a string")
    normalized = code.strip().upper()
    if not normalized.startswith(code_format.prefix.upper()):
        raise TeamCodeError(f"expected version prefix {code_format.prefix}")
    if not normalized.endswith(code_format.set_id.upper()):
        raise TeamCodeError(f"expected set suffix {code_format.set_id}")

    payload_end = len(normalized) - len(code_format.set_id)
    payload = normalized[len(code_format.prefix):payload_end]
    expected_payload_length = code_format.slot_count * 3
    if len(payload) != expected_payload_length:
        raise TeamCodeError(
            f"expected {code_format.slot_count} three-digit planner IDs"
        )

    slots: list[TeamSlot] = []
    for offset in range(0, len(payload), 3):
        raw_planner_code = payload[offset:offset + 3]
        try:
            planner_code = int(raw_planner_code, 16)
        except ValueError as error:
            raise TeamCodeError(f"invalid planner ID: {raw_planner_code}") from error
        candidates = tuple(planner_to_units.get(planner_code, ()))
        unit_id = candidates[0] if len(candidates) == 1 else None
        slots.append(TeamSlot(planner_code, unit_id, candidates))

    return DecodedTeam(
        code_format=code_format,
        slots=tuple(slots),
        raw_code=normalized,
    )


def encode_team_code(
    team: DecodedTeam,
    unit_to_planner_code: Mapping[str, int],
) -> str:
    """Encode an edited team back to the client import format."""
    planner_codes: list[int] = []
    for slot in team.slots:
        planner_code = slot.planner_code
        if slot.unit_id is not None:
            try:
                planner_code = unit_to_planner_code[slot.unit_id]
            except KeyError as error:
                raise TeamCodeError(f"unknown catalog unit: {slot.unit_id}") from error
        if not isinstance(planner_code, int) or not 0 <= planner_code <= MAX_PLANNER_CODE:
            raise TeamCodeError("planner codes must fit in 12 bits")
        planner_codes.append(planner_code)

    payload = "".join(f"{planner_code:03X}" for planner_code in planner_codes)
    return f"{team.code_format.prefix.upper()}{payload}{team.code_format.set_id}"


def encode_unit_ids(
    unit_ids: Sequence[str | None],
    unit_to_planner_code: Mapping[str, int],
    *,
    code_format: TeamCodeFormat = DEFAULT_TEAM_CODE_FORMAT,
) -> str:
    """Encode catalog IDs, padding the format's remaining slots as empty."""
    if len(unit_ids) > code_format.slot_count:
        raise TeamCodeError(
            f"a team can contain at most {code_format.slot_count} encoded units"
        )
    slots = []
    for unit_id in unit_ids:
        if unit_id is None:
            slots.append(TeamSlot(EMPTY_PLANNER_CODE))
            continue
        try:
            planner_code = unit_to_planner_code[unit_id]
        except KeyError as error:
            raise TeamCodeError(f"unknown catalog unit: {unit_id}") from error
        slots.append(TeamSlot(planner_code, unit_id, (unit_id,)))
    slots.extend(
        TeamSlot(EMPTY_PLANNER_CODE)
        for _ in range(code_format.slot_count - len(slots))
    )
    team = DecodedTeam(code_format, tuple(slots), "")
    return encode_team_code(team, unit_to_planner_code)
