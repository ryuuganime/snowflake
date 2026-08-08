# SPDX-License-Identifier: MIT
import hashlib
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import IntEnum

RYUUGANIME_EPOCH = 1782864000000
SPEC_VERSION = 0
MOD_64_BIT = 1 << 64
MASK_64_BIT = MOD_64_BIT - 1

BASE62_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


class EntityType(IntEnum):
    USER = 0
    USER_LIST = 1
    MEDIA = 4
    RELEASE_INFO = 5
    ENTITY = 6
    RELATIONSHIP = 7
    MAPPINGS = 8
    COMMUNITY = 11
    CLIENT = 14
    NOTIFICATION = 15
    FEEDBACK = 16
    LOG = 17
    CDN_MEDIA_ASSET = 18
    INTERACTION = 19
    DISTRIBUTION_FILES = 20
    UNCATEGORIZED = 31


def _st(type_id: int, subtype_id: int) -> int:
    return (type_id << 4) | subtype_id


class Subtype(IntEnum):
    """Combined type+subtype (9 bits). Each value encodes (type << 4) | subtype."""

    USER_ACCOUNT = _st(0, 0)
    USER_ACTIVITY = _st(0, 1)
    USER_SCROBBLE = _st(0, 2)
    USER_POST = _st(0, 3)
    USER_COMMENT = _st(0, 4)
    USER_DM_THREAD = _st(0, 5)
    USER_DM_REPLY = _st(0, 6)
    USER_REVIEW = _st(0, 7)
    USER_LIST_CURRENT = _st(1, 0)
    USER_LIST_COMPLETED = _st(1, 1)
    USER_LIST_PLANNED = _st(1, 2)
    USER_LIST_PAUSED = _st(1, 3)
    USER_LIST_DROPPED = _st(1, 4)
    USER_LIST_HIDDEN = _st(1, 5)
    USER_LIST_COLLECTED = _st(1, 6)
    USER_LIST_FAVORITE = _st(1, 7)
    USER_LIST_ENTRY = _st(1, 8)
    USER_LIST_REACTIONS = _st(1, 9)
    USER_LIST_CUSTOM = _st(1, 15)
    MEDIA_FRANCHISE = _st(4, 0)
    MEDIA_SHOW = _st(4, 1)
    MEDIA_BOOK = _st(4, 2)
    MEDIA_MUSIC = _st(4, 3)
    MEDIA_SEASON = _st(4, 6)
    MEDIA_COUR = _st(4, 7)
    MEDIA_EPISODE = _st(4, 8)
    RELEASE_PLATFORM = _st(5, 0)
    RELEASE_SCHEDULE = _st(5, 1)
    RELEASE_EVENT = _st(5, 2)
    ENTITY_PERSON = _st(6, 0)
    ENTITY_CHARACTER = _st(6, 1)
    ENTITY_COMPANY = _st(6, 2)
    RELATIONSHIP_GENRE = _st(7, 0)
    RELATIONSHIP_THEME = _st(7, 1)
    RELATIONSHIP_ROLE = _st(7, 2)
    RELATIONSHIP_AWARD = _st(7, 3)
    RELATIONSHIP_RELATED = _st(7, 4)
    MAPPING_EXTERNAL = _st(8, 0)
    MAPPING_INTERNAL = _st(8, 1)
    COMMUNITY_GROUP = _st(11, 0)
    COMMUNITY_GROUP_MSG = _st(11, 1)
    COMMUNITY_FORUM = _st(11, 2)
    COMMUNITY_NEWS = _st(11, 3)
    COMMUNITY_EVENT = _st(11, 4)
    COMMUNITY_POLL = _st(11, 5)
    CLIENT_FIRST_PARTY = _st(14, 0)
    CLIENT_THIRD_PARTY = _st(14, 1)
    CLIENT_SESSION = _st(14, 2)
    NOTIFICATION_SYSTEM = _st(15, 0)
    NOTIFICATION_IN_APP = _st(15, 1)
    NOTIFICATION_WEBHOOK = _st(15, 2)
    FEEDBACK_THREAD = _st(16, 0)
    FEEDBACK_REPLY = _st(16, 1)
    FEEDBACK_ACTION = _st(16, 2)
    LOG_REVISION = _st(17, 0)
    LOG_USER = _st(17, 1)
    LOG_MOD = _st(17, 2)
    LOG_SYSTEM = _st(17, 3)
    CDN_SITE_ASSET = _st(18, 0)
    CDN_PROFILE_PICTURE = _st(18, 1)
    CDN_POSTER = _st(18, 2)
    CDN_BACKDROP = _st(18, 3)
    CDN_LOGO = _st(18, 4)
    CDN_USER_ASSETS = _st(18, 5)
    CDN_PROMO = _st(18, 6)
    INTERACTION_MILESTONE = _st(19, 0)
    INTERACTION_ACHIEVEMENT = _st(19, 1)
    DISTRIBUTION_PROVIDER = _st(20, 0)
    DISTRIBUTION_MEDIA_FILE = _st(20, 1)
    UNCATEGORIZED = _st(31, 15)


def compute_node_fingerprint(system_identity: str) -> int:
    sha256_hash = hashlib.sha256(system_identity.encode("utf-8")).digest()
    raw_int = int.from_bytes(sha256_hash, byteorder="big")
    return raw_int % MOD_64_BIT


def encode_base62(num: int, pad: bool = False) -> str:
    if num < 0 or num >= (1 << 128):
        raise ValueError("Cannot encode numbers outside 128-bit unsigned range.")
    if num == 0:
        return "0" * 22 if pad else "0"
    chars = []
    while num > 0:
        num, rem = divmod(num, 62)
        chars.append(BASE62_ALPHABET[rem])
    b62_str = "".join(reversed(chars))
    return b62_str.zfill(22) if pad else b62_str


def decode_base62(b62_str: str) -> int:
    if not b62_str:
        raise ValueError("Base62 string cannot be empty.")
    num = 0
    for char in b62_str:
        if char not in BASE62_ALPHABET:
            raise ValueError(f"Invalid Base62 character: '{char}'")
        num = num * 62 + BASE62_ALPHABET.index(char)
    if num >= (1 << 128):
        raise ValueError("Decoded Base62 integer exceeds 128-bit unsigned range.")
    return num


def _millis_to_datetime(millis: int) -> datetime:
    return datetime.fromtimestamp(millis / 1000.0, tz=timezone.utc)


@dataclass(frozen=True, slots=True)
class SnowflakeComponents:
    """Parsed components of a Ryuuganime Snowflake ID.

    type and subtype are raw ints. Use EntityType(type) or Subtype(subtype)
    to cast to enum when you know the value is valid.
    """

    version: int
    timestamp: datetime
    type: int
    subtype: int
    sequence: int
    node_fingerprint: int

    @property
    def type_id(self) -> int:
        """Raw 5-bit type value."""
        return self.type

    @property
    def subtype_id(self) -> int:
        """Raw 4-bit subtype value (lower 4 bits of subtype)."""
        return self.subtype & 0xF

    def to_dict(self) -> dict[str, int]:
        return {
            "version": self.version,
            "timestamp": int(self.timestamp.timestamp() * 1000),
            "type": self.type,
            "subtype": self.subtype,
            "sequence": self.sequence,
            "node_fingerprint": self.node_fingerprint,
        }


@dataclass(frozen=True, slots=True)
class Snowflake:
    _raw: int

    def to_string(self, pad: bool = False) -> str:
        return encode_base62(self._raw, pad=pad)

    def to_bytes(self) -> bytes:
        return self._raw.to_bytes(16, byteorder="big")

    def to_int(self) -> int:
        return self._raw

    @property
    def components(self) -> SnowflakeComponents:
        ts_millis = ((self._raw >> 83) & 0x3FFFFFFFFFF) + RYUUGANIME_EPOCH
        return SnowflakeComponents(
            version=(self._raw >> 125) & 0x7,
            timestamp=_millis_to_datetime(ts_millis),
            type=(self._raw >> 78) & 0x1F,
            subtype=(self._raw >> 74) & 0x1FF,
            sequence=(self._raw >> 64) & 0x3FF,
            node_fingerprint=self._raw & MASK_64_BIT,
        )

    def __str__(self) -> str:
        return self.to_string()

    def __repr__(self) -> str:
        return f"Snowflake({self.to_string()})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Snowflake):
            return self._raw == other._raw
        return NotImplemented

    def __lt__(self, other: "Snowflake") -> bool:
        if isinstance(other, Snowflake):
            return self._raw < other._raw
        return NotImplemented

    def __le__(self, other: "Snowflake") -> bool:
        if isinstance(other, Snowflake):
            return self._raw <= other._raw
        return NotImplemented

    def __gt__(self, other: "Snowflake") -> bool:
        if isinstance(other, Snowflake):
            return self._raw > other._raw
        return NotImplemented

    def __ge__(self, other: "Snowflake") -> bool:
        if isinstance(other, Snowflake):
            return self._raw >= other._raw
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._raw)


class RyuuganimeSnowflake:
    def __init__(
        self,
        system_identity: str | None = None,
        raw_fingerprint: int | None = None,
        max_rollback_ms: int = 10,
    ):
        if not (0 <= max_rollback_ms <= 1000):
            raise ValueError("max_rollback_ms must be between 0 and 1000 ms.")
        if raw_fingerprint is not None:
            if raw_fingerprint < 0:
                raise ValueError("raw_fingerprint must be a non-negative integer.")
            self.node_fingerprint = raw_fingerprint % MOD_64_BIT
        elif system_identity is not None:
            self.node_fingerprint = compute_node_fingerprint(system_identity)
        else:
            raise ValueError(
                "Must provide either system_identity string or raw_fingerprint int."
            )
        self.sequence = 0
        self.last_timestamp = -1
        self.max_rollback_ms = max_rollback_ms
        self._lock = threading.Lock()
        self._last_was_override = False

    def generate_raw(
        self,
        type_id: int,
        subtype_id: int,
        current_ts: int | None = None,
        version: int = SPEC_VERSION,
    ) -> int:
        if not (0 <= version <= 7):
            raise ValueError("Version must be between 0 and 7 (3 bits).")
        if not (0 <= type_id <= 31):
            raise ValueError("Type ID must be between 0 and 31 (5 bits).")
        if not (0 <= subtype_id <= 15):
            raise ValueError("Subtype ID must be between 0 and 15 (4 bits).")
        with self._lock:
            is_ts_override = current_ts is not None
            ts = current_ts if is_ts_override else int(time.time() * 1000)
            if ts < self.last_timestamp:
                diff = self.last_timestamp - ts
                if diff <= self.max_rollback_ms:
                    time.sleep(diff / 1000.0)
                    ts = int(time.time() * 1000)
                else:
                    raise RuntimeError(f"Clock moved backwards by {diff}ms.")
            if is_ts_override:
                self.sequence = (self.sequence + 1) & 0x3FF
                if self.sequence == 0:
                    while ts <= self.last_timestamp:
                        time.sleep(0.001)
                        ts = int(time.time() * 1000)
                    self.sequence = 0
                self._last_was_override = True
            else:
                if ts == self.last_timestamp and not self._last_was_override:
                    self.sequence = (self.sequence + 1) & 0x3FF
                    if self.sequence == 0:
                        while ts <= self.last_timestamp:
                            time.sleep(0.001)
                            ts = int(time.time() * 1000)
                        self.sequence = 0
                else:
                    self.sequence = 0
                self._last_was_override = False
                self.last_timestamp = ts
            time_diff = ts - RYUUGANIME_EPOCH
            if time_diff < 0:
                raise ValueError("Current time is before the Ryuuganime epoch.")
            if time_diff >= (1 << 42):
                raise ValueError("Timestamp overflow.")
            return (
                (version << 125)
                | (time_diff << 83)
                | (type_id << 78)
                | (subtype_id << 74)
                | (self.sequence << 64)
                | self.node_fingerprint
            )

    def generate(
        self,
        subtype: Subtype,
        current_ts: int | None = None,
        version: int = SPEC_VERSION,
    ) -> Snowflake:
        type_id = (int(subtype) >> 4) & 0x1F
        subtype_id = int(subtype) & 0xF
        raw = self.generate_raw(
            type_id=type_id,
            subtype_id=subtype_id,
            current_ts=current_ts,
            version=version,
        )
        return Snowflake(raw)

    def generate_bytes(
        self,
        subtype: Subtype,
        current_ts: int | None = None,
        version: int = SPEC_VERSION,
    ) -> bytes:
        return self.generate(
            subtype=subtype, current_ts=current_ts, version=version
        ).to_bytes()

    @staticmethod
    def parse(snowflake_val: str | int | bytes) -> Snowflake:
        if isinstance(snowflake_val, Snowflake):
            return snowflake_val
        if isinstance(snowflake_val, str):
            if not snowflake_val:
                raise ValueError("Base62 Snowflake string cannot be empty.")
            if len(snowflake_val) < 11 or len(snowflake_val) > 22:
                raise ValueError(
                    "Base62 Snowflake string must be between 11 and 22 characters long."
                )
            num = decode_base62(snowflake_val)
        elif isinstance(snowflake_val, bytes):
            if len(snowflake_val) != 16:
                raise ValueError("Snowflake bytes must be exactly 16 bytes long.")
            num = int.from_bytes(snowflake_val, byteorder="big")
        elif isinstance(snowflake_val, int):
            if not (0 <= snowflake_val < (1 << 128)):
                raise ValueError("Snowflake integer must fit within 128 bits unsigned.")
            num = snowflake_val
        else:
            raise TypeError("Snowflake value must be a str, int, bytes, or Snowflake.")
        return Snowflake(num)


if __name__ == "__main__":
    import argparse
    import sys

    SUBTYPE_LOOKUP = {s.name: s for s in Subtype}

    def _make_generator() -> RyuuganimeSnowflake:
        return RyuuganimeSnowflake(
            system_identity="worker-01|prod-node-01.ryuuganime.local|mac:00:1A:2B:3C:4D:5E",
            max_rollback_ms=10,
        )

    def _print_sf(sf: Snowflake) -> None:
        c = sf.components
        type_name = (
            EntityType(c.type).name
            if c.type in EntityType._value2member_map_
            else f"RESERVED({c.type})"
        )
        print(f"  Base62:       {sf.to_string()}")
        print(f"  Padded:       {sf.to_string(pad=True)}")
        print(f"  Bytes:        {sf.to_bytes().hex()}")
        print(f"  Int:          {sf.to_int()}")
        print(f"  Version:      {c.version}")
        print(f"  Timestamp:    {c.timestamp}")
        print(f"  Type:         {c.type} ({type_name})")
        sub_raw = c.subtype & 0xF
        sub_name = (
            Subtype(c.subtype).name if c.subtype in Subtype._value2member_map_ else None
        )
        if sub_name:
            print(f"  Subtype:      {sub_raw} {sub_name} (combined={c.subtype})")
        else:
            print(f"  Subtype:      {sub_raw}")
        print(f"  Sequence:     {c.sequence}")
        print(f"  Node FP:      {c.node_fingerprint}")

    def cmd_generate(args: argparse.Namespace) -> None:
        sf = _make_generator().generate(subtype=SUBTYPE_LOOKUP[args.subtype])
        _print_sf(sf)

    def cmd_parse(args: argparse.Namespace) -> None:
        raw = args.value
        try:
            raw = int(raw)
        except ValueError:
            pass
        sf = RyuuganimeSnowflake.parse(raw)
        _print_sf(sf)

    def cmd_interactive() -> None:
        print("Ryuuganime Snowflake ID Generator\n")
        print("  1) Generate")
        print("  2) Parse")
        choice = input("\nChoice [1]: ").strip() or "1"

        if choice == "2":
            val = input("Enter snowflake (Base62 string or int): ").strip()
            try:
                val = int(val)
            except ValueError:
                pass
            sf = RyuuganimeSnowflake.parse(val)
            print()
            _print_sf(sf)
            return

        print(f"\nAvailable subtypes ({len(SUBTYPE_LOOKUP)}):")
        for i, name in enumerate(SUBTYPE_LOOKUP):
            print(f"  {i + 1:3d}) {name}", end="")
            if (i + 1) % 3 == 0:
                print()
        print()
        sub_name = input("Subtype name: ").strip().upper()
        if sub_name not in SUBTYPE_LOOKUP:
            print(f"Unknown subtype: {sub_name}", file=sys.stderr)
            sys.exit(1)
        sf = _make_generator().generate(subtype=SUBTYPE_LOOKUP[sub_name])
        print()
        _print_sf(sf)

    parser = argparse.ArgumentParser(description="Ryuuganime Snowflake ID tool")
    sub = parser.add_subparsers(dest="command")

    p_gen = sub.add_parser("generate", help="Generate a new Snowflake ID")
    p_gen.add_argument(
        "subtype",
        choices=SUBTYPE_LOOKUP.keys(),
        help="Subtype enum name (e.g. USER_ACCOUNT, MEDIA_SEASON)",
    )
    p_gen.set_defaults(func=cmd_generate)

    p_parse = sub.add_parser("parse", help="Parse a Snowflake ID into components")
    p_parse.add_argument("value", help="Base62 string, raw int, or 16-byte hex")
    p_parse.set_defaults(func=cmd_parse)

    args = parser.parse_args()
    if args.command is None:
        cmd_interactive()
    else:
        args.func(args)
