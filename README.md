# Ryuuganime Snowflake ID

A 128-bit decentralized, time-ordered identifier designed for distributed database architectures and high-performance B-Tree indexing.

## Overview

Ryuuganime Snowflake IDs solve a simple problem: generating unique, sortable IDs across multiple services without a central authority.

Each ID is a 128-bit unsigned integer containing a version, timestamp, entity type, sequence number, and a node fingerprint derived from the host machine's identity. IDs sort chronologically at the database level when stored as raw bytes (`BYTEA` / `BINARY(16)`), and compact to 11-22 character Base62 strings for URLs and APIs.

Custom epoch: `2026-07-01T00:00:00Z`

## Repository Contents

| File | Description |
|:--|:--|
| `SNOWFLAKE_SPEC.md` | Formal specification (RFC-style, with bit layout, generation rules, type registry) |
| `sample.py` | Reference Python implementation (sync, thread-safe) |

## Usage

```python
from sample import RyuuganimeSnowflake, Subtype, EntityType

gen = RyuuganimeSnowflake(
    system_identity="worker-01|prod-node-01.example.com|mac:00:1A:2B:3C:4D:5E"
)

# Generate a Snowflake ID using a Subtype enum (carries type + subtype)
sf = gen.generate(subtype=Subtype.USER_ACCOUNT)

# Convert on the fly
sf.to_string()  # Base62, unpadded: "czQ8he9i7t9xg9nP"
sf.to_string(pad=True)  # Base62, padded to 22 chars
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

# Parse any representation back
sf2 = RyuuganimeSnowflake.parse("czQ8he9i7t9xg9nP")
sf2.to_bytes()

# Snowflake objects are comparable and hashable
sf < sf2  # True if sf was generated earlier
```

### CLI

```
python sample.py generate USER_ACCOUNT
python sample.py generate MEDIA_SEASON
python sample.py parse czQ8he9i7t9xg9nP
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
- Base62 encoding/decoding and case sensitivity
- Database ingestion boundaries
- Node fingerprint computation and collision handling
- Complete type/subtype registry
