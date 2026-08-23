# Ryuuganime Snowflake ID

A 128-bit decentralized, time-ordered identifier designed for distributed database architectures and high-performance B-Tree indexing.

## Overview

Ryuuganime Snowflake IDs solve a simple problem: generating unique, sortable IDs across multiple services without a central authority.

Each ID is a 128-bit unsigned integer containing a version, timestamp, entity type, sequence number, and a node fingerprint derived from the host machine's identity. IDs sort chronologically at the database level when stored as raw bytes (`BYTEA` / `BINARY(16)`), and compact to **Base64** strings (`=`, `_`, `0-9`, `A-Z`, `a-z`) for URLs/APIs — **22-char padded for DB (strict ASCII/UTF-8 sortable)** and **1–22-char trimmed for client display** (strip leading `0`s).

Custom epoch: `2026-07-01T00:00:00Z`

**Encoding guarantee:** Alphabet `0123456789=ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz` is ordered by ASCII codepoint. **DB-padded 22** ensures lexicographic bytewise order == integer order; **client-trimmed 1–22** (strip leading `0`s) MUST be re-padded to 22 before DB sort/storage. Case-sensitive (`A` ≠ `a`).

## Repository Contents

| File | Description |
|:--|:--|
| `SNOWFLAKE_SPEC.md` | Formal specification (RFC-style, with bit layout, generation rules, type registry, Base64 sortable) |
| `sample.py` | Reference Python implementation (sync, thread-safe, Base64 sortable 22-char) |

## Usage

```python
from sample import RyuuganimeSnowflake, Subtype, EntityType

gen = RyuuganimeSnowflake(
    system_identity="worker-01|prod-node-01.example.com|mac:00:1A:2B:3C:4D:5E"
)

# Generate a Snowflake ID using a Subtype enum (carries type + subtype)
sf = gen.generate(subtype=Subtype.USER_ACCOUNT)

# Convert on the fly — always 22 chars, sortable, case-sensitive
sf.to_string()  # Base64 sortable, padded to 22 chars: e.g. "000A1b2C3d4E5f6G7h8I9jK0"
sf.to_string(pad=True)  # same (fixed width; pad param kept for compat)
sf.to_bytes()  # 16 bytes for BYTEA / BINARY(16)
sf.to_int()  # raw 128-bit integer

# Access individual fields -- timestamp is a timezone-aware datetime
c = sf.components
c.version  # 0
c.timestamp  # datetime(2026, 7, 1, 0, 0, 1, tzinfo=UTC)
c.type  # 0 (raw int -- cast with EntityType(c.type) if known valid)
c.subtype  # 0 (raw int -- cast with Subtype(c.subtype) if known valid)
c.type_id  # same as c.type
c.subtype_id  # lower 4 bits of c.subtype
c.sequence  # 1
c.node_fingerprint  # node-specific

# Parse any representation back — string MUST be exactly 22 chars
sf2 = RyuuganimeSnowflake.parse("000A1b2C3d4E5f6G7h8I9jK0")
sf2.to_bytes()

# Snowflake objects are comparable and hashable; string sort == int sort
sf < sf2  # True if sf was generated earlier
sorted([sf2.to_string(), sf.to_string()]) == sorted([sf2.to_int(), sf.to_int()], key=lambda x: x if isinstance(x,int) else x)  # invariant holds for 22-char sortable encoding
```

### CLI

```
python sample.py generate USER_ACCOUNT
python sample.py generate MEDIA_SEASON
python sample.py parse 000A1b2C3d4E5f6G7h8I9jK0
```

Run with no args for interactive mode.

### Subtype enum

`Subtype` values encode `(type << 4) | subtype` as a single 9-bit integer, ready for bitfield assembly:

```python
Subtype.MEDIA_SEASON  # value = 70 = 0b1000110
(int(Subtype.MEDIA_SEASON) >> 4)  # => 4 (EntityType.MEDIA)
int(Subtype.MEDIA_SEASON) & 0xF  # => 6 (Season)
```

`SnowflakeComponents.type` and `.subtype` are raw ints so they work for any valid 5-bit/9-bit value, including reserved type IDs not defined in `EntityType`.

## Bit Layout

```
127          125 124                          83 82       78 77          74 73              64 63                             0
+---------------+-------------------------------+-----------+--------------+------------------+-------------------------------+
| Version       | Timestamp                     | Type      | Subtype      | Sequence         | Node Fingerprint              |
| (3 bits)      | (42 bits)                     | (5 bits)  | (4 bits)     | (10 bits)        | (64 bits)                     |
+---------------+-------------------------------+-----------+--------------+------------------+-------------------------------+
```

- **Version** (3 bits): Layout version. Currently `0`.
- **Timestamp** (42 bits): Milliseconds since epoch. Valid for ~139 years.
- **Type** (5 bits): Entity domain (User, Media, Community, etc.).
- **Subtype** (4 bits): Role within that domain.
- **Sequence** (10 bits): Per-millisecond rolling counter (up to 1,024 IDs/ms per node).
- **Node Fingerprint** (64 bits): SHA-256 hash of the host identity, modulo 2^64.

## Text Encoding — Base64 Sortable

| Property | Value |
|:--|:--|
| **Alphabet** | `0123456789=ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz` (64 symbols, ASCII-sorted, strict UTF-8 sortable, case-sensitive) |
| **Characters** | `A-Z` (65-90), `a-z` (97-122), `0-9` (48-57), `=` (61), `_` (95) |
| **Width** | **DB: exactly 22** (132 bits, padded with `0`, sortable) / **Client: 1–22 trimmed** (strip leading `0`s) |
| **Regex** | `^[0-9A-Z_a-z=]{22}$` — case-sensitive, exactly 22, no `+`/`/`/`-` |
| **Sortable** | `uint128` order == UTF-8 bytewise lex order **only when padded to 22** (`sorted(padded) == sorted(ints)`) |
| **Case** | `A` ≠ `a`; boundaries MUST NOT fold case |

See `SNOWFLAKE_SPEC.md` Section 5 for formal definition and migration note from Base62.

## Type and Subtype Registry

| Type | Name | Subtypes |
|:--|:--|:--|
| 0 | User | Account, Activity, Scrobble, Post, Comment, DM Thread, DM Reply, Review |
| 1 | User List | Current, Completed, Planned, Paused, Dropped, Hidden, Collected, Favorite, Entry, Reactions |
| 4 | Media | Franchise, Show/Movie, Book, Music, Season, Cour, Episode |
| 5 | Release Info | Platform, Schedule, Event |
| 6 | Entity | Person, Character, Company |
| 7 | Relationship | Genre, Theme, Role, Award, Related Title |
| 8 | Mappings | External Platform, Mapping |
| 11 | Community | Group, Group Message, Forum Thread, News, Event, Poll |
| 14 | Client | First Party, Third Party, Session |
| 15 | Notification | System, In-App, Webhook |
| 16 | Feedback | Thread, Reply, Action |
| 17 | Log | Revision Log, User Log, Mod Log, System Log |
| 18 | CDN / Media Asset | Site Asset, Profile Picture, Poster, Backdrop, Logo, User Assets, Promo |
| 19 | Interaction | Milestone, Achievement/Badge |
| 20 | Distribution & Files | Provider, Media File |
| 31 | Uncategorized | Uncategorized |

See `SNOWFLAKE_SPEC.md` Section 6 for the complete registry including reserved ranges.

## License

| Component | License | SPDX |
|:--|:--|:--|
| Code (`sample.py`) | [MIT](LICENSE.MIT) | `MIT` |
| Specification (`SNOWFLAKE_SPEC.md`) | [CC-BY-4.0](LICENSE) | `CC-BY-4.0` |

## Specification

The full formal specification is in [`SNOWFLAKE_SPEC.md`](SNOWFLAKE_SPEC.md). It covers:

- Generation lifecycle and thread safety requirements
- Clock rollback tolerance rules
- Base64 sortable encoding/decoding, strict ASCII/UTF-8 sortable & case sensitivity
- Database ingestion boundaries
- Node fingerprint computation and collision handling
- Complete type/subtype registry
