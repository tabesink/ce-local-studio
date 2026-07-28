"""Path 1 schema compatibility: pg_catalog inventory, snapshot, and closed reasons.

Migrate preflight and startup readiness share one reconciler with different
accept policies (empty allowed only on the migrate path).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from context_engine.schema_deferred import DEFERRED_WIKI_COLUMNS, DEFERRED_WIKI_TABLES


Policy = Literal["migrate", "startup"]


def _supported_head() -> str:
    # Lazy import avoids circular dependency with readiness → schema_compatibility.
    from context_engine.services.readiness import SUPPORTED_ALEMBIC_HEAD

    return SUPPORTED_ALEMBIC_HEAD

REASON_EMPTY_OK = "empty_ok"
REASON_CURRENT_TARGET_OK = "current_target_ok"
REASON_LEGACY = "legacy_database_refused"
REASON_PARTIAL = "partial_schema"
REASON_RENAMED = "renamed_object"
REASON_UNKNOWN_OBJECT = "unknown_object"
REASON_UNKNOWN_HISTORY = "unknown_history"
REASON_BEHIND = "revision_behind"
REASON_AHEAD = "revision_ahead"
REASON_EXTENSION = "extension_refused"
REASON_CATALOG_MISMATCH = "catalog_mismatch"
REASON_SNAPSHOT_HEAD_MISMATCH = "snapshot_head_mismatch"

# Fresh PostgreSQL 16 cluster / template0 baseline for Compose postgres:16.
ALLOWED_EXTENSIONS: frozenset[tuple[str, str]] = frozenset({("plpgsql", "1.0")})
ALLOWED_SCHEMAS: frozenset[str] = frozenset(
    {"pg_catalog", "information_schema", "pg_toast", "public"}
)

SNAPSHOT_DIR = Path(__file__).resolve().parents[1] / "schema_snapshots"


@dataclass(frozen=True)
class CatalogInventory:
    """Normalized, sorted catalog projection used for exact-match compare."""

    alembic_revision: str | None
    extensions: tuple[tuple[str, str], ...]
    schemas: tuple[str, ...]
    relations: tuple[tuple[str, str, str], ...]  # schema, name, kind
    columns: tuple[tuple[str, str, str, str], ...]  # schema, table, column, type
    constraints: tuple[tuple[str, str, str, str], ...]  # schema, table, name, type
    indexes: tuple[tuple[str, str, str, str], ...]  # schema, table, name, def
    enums: tuple[tuple[str, str, tuple[str, ...]], ...]  # schema, name, labels
    triggers: tuple[tuple[str, str, str], ...]  # schema, table, name
    routines: tuple[tuple[str, str, str], ...]  # schema, name, identity args

    def fingerprint(self) -> str:
        """Stable hash input for mutation-zero proofs (excludes revision)."""
        payload = {
            "extensions": self.extensions,
            "schemas": self.schemas,
            "relations": self.relations,
            "columns": self.columns,
            "constraints": self.constraints,
            "indexes": self.indexes,
            "enums": self.enums,
            "triggers": self.triggers,
            "routines": self.routines,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class CompatibilityVerdict:
    reason: str
    accepted: bool


def snapshot_path_for_head(head: str | None = None) -> Path:
    return SNAPSHOT_DIR / f"{head or _supported_head()}.json"


def load_expected_snapshot(head: str | None = None) -> CatalogInventory:
    head = head or _supported_head()
    path = snapshot_path_for_head(head)
    if not path.is_file():
        raise FileNotFoundError(f"Missing schema snapshot for head {head}: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    meta_head = raw.get("alembic_head")
    if meta_head != head:
        raise ValueError(f"snapshot_head_mismatch: file claims {meta_head!r}, expected {head!r}")
    return _inventory_from_dict(raw["inventory"])


def dump_snapshot(inventory: CatalogInventory, head: str | None = None) -> dict[str, Any]:
    resolved = head or _supported_head()
    return {
        "alembic_head": resolved,
        "inventory": _inventory_to_dict(inventory),
    }


def write_snapshot(inventory: CatalogInventory, head: str | None = None) -> Path:
    head = head or _supported_head()
    path = snapshot_path_for_head(head)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dump_snapshot(inventory, head), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def collect_inventory(connection: Connection) -> CatalogInventory:
    """Collect a normalized inventory over a read-only connection."""
    revision = _alembic_revision(connection)
    extensions = tuple(
        sorted(
            (str(name), str(version))
            for name, version in connection.execute(
                text("SELECT extname, extversion FROM pg_extension")
            )
        )
    )
    schemas = tuple(
        sorted(
            set(
                str(name)
                for (name,) in connection.execute(
                    text(
                        "SELECT nspname FROM pg_namespace "
                        "WHERE nspname NOT IN ('pg_catalog', 'information_schema') "
                        "AND nspname NOT LIKE 'pg\\_%' ESCAPE '\\'"
                    )
                )
            )
            | {"public"}
        )
    )

    relations = tuple(
        sorted(
            (str(schema), str(name), str(kind))
            for schema, name, kind in connection.execute(
                text(
                    """
                    SELECT n.nspname, c.relname,
                           CASE c.relkind
                             WHEN 'r' THEN 'table'
                             WHEN 'p' THEN 'partitioned_table'
                             WHEN 'v' THEN 'view'
                             WHEN 'm' THEN 'materialized_view'
                             WHEN 'S' THEN 'sequence'
                             WHEN 'f' THEN 'foreign_table'
                             ELSE c.relkind::text
                           END
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = ANY(:schemas)
                      AND c.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
                      AND NOT c.relispartition
                    """
                ),
                {"schemas": list(schemas)},
            )
        )
    )

    columns = tuple(
        sorted(
            (str(schema), str(table), str(column), str(data_type))
            for schema, table, column, data_type in connection.execute(
                text(
                    """
                    SELECT n.nspname, c.relname, a.attname,
                           pg_catalog.format_type(a.atttypid, a.atttypmod)
                    FROM pg_attribute a
                    JOIN pg_class c ON c.oid = a.attrelid
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = ANY(:schemas)
                      AND c.relkind IN ('r', 'p', 'v', 'm')
                      AND a.attnum > 0
                      AND NOT a.attisdropped
                      AND NOT c.relispartition
                    """
                ),
                {"schemas": list(schemas)},
            )
        )
    )

    constraints = tuple(
        sorted(
            (str(schema), str(table), str(name), str(contype))
            for schema, table, name, contype in connection.execute(
                text(
                    """
                    SELECT n.nspname, rel.relname, con.conname,
                           CASE con.contype
                             WHEN 'p' THEN 'primary'
                             WHEN 'u' THEN 'unique'
                             WHEN 'f' THEN 'foreign'
                             WHEN 'c' THEN 'check'
                             WHEN 'x' THEN 'exclusion'
                             ELSE con.contype::text
                           END
                    FROM pg_constraint con
                    JOIN pg_class rel ON rel.oid = con.conrelid
                    JOIN pg_namespace n ON n.oid = rel.relnamespace
                    WHERE n.nspname = ANY(:schemas)
                      AND NOT rel.relispartition
                    """
                ),
                {"schemas": list(schemas)},
            )
        )
    )

    indexes = tuple(
        sorted(
            (str(schema), str(table), str(name), str(indexdef))
            for schema, table, name, indexdef in connection.execute(
                text(
                    """
                    SELECT n.nspname, t.relname, i.relname,
                           pg_get_indexdef(i.oid)
                    FROM pg_class i
                    JOIN pg_index x ON x.indexrelid = i.oid
                    JOIN pg_class t ON t.oid = x.indrelid
                    JOIN pg_namespace n ON n.oid = t.relnamespace
                    WHERE n.nspname = ANY(:schemas)
                      AND i.relkind = 'i'
                      AND NOT t.relispartition
                    """
                ),
                {"schemas": list(schemas)},
            )
        )
    )

    enums: list[tuple[str, str, tuple[str, ...]]] = []
    for schema, name in connection.execute(
        text(
            """
            SELECT n.nspname, t.typname
            FROM pg_type t
            JOIN pg_namespace n ON n.oid = t.typnamespace
            WHERE t.typtype = 'e'
              AND n.nspname = ANY(:schemas)
            """
        ),
        {"schemas": list(schemas)},
    ):
        labels = tuple(
            str(label)
            for (label,) in connection.execute(
                text(
                    """
                    SELECT e.enumlabel
                    FROM pg_enum e
                    JOIN pg_type t ON t.oid = e.enumtypid
                    JOIN pg_namespace n ON n.oid = t.typnamespace
                    WHERE n.nspname = :schema AND t.typname = :name
                    ORDER BY e.enumsortorder
                    """
                ),
                {"schema": schema, "name": name},
            )
        )
        enums.append((str(schema), str(name), labels))
    enums_t = tuple(sorted(enums, key=lambda item: (item[0], item[1])))

    triggers = tuple(
        sorted(
            (str(schema), str(table), str(name))
            for schema, table, name in connection.execute(
                text(
                    """
                    SELECT n.nspname, c.relname, t.tgname
                    FROM pg_trigger t
                    JOIN pg_class c ON c.oid = t.tgrelid
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = ANY(:schemas)
                      AND NOT t.tgisinternal
                      AND NOT c.relispartition
                    """
                ),
                {"schemas": list(schemas)},
            )
        )
    )

    routines = tuple(
        sorted(
            (str(schema), str(name), str(identity))
            for schema, name, identity in connection.execute(
                text(
                    """
                    SELECT n.nspname, p.proname, pg_get_function_identity_arguments(p.oid)
                    FROM pg_proc p
                    JOIN pg_namespace n ON n.oid = p.pronamespace
                    WHERE n.nspname = ANY(:schemas)
                      AND p.prokind IN ('f', 'p')
                      AND NOT EXISTS (
                        SELECT 1 FROM pg_depend d
                        JOIN pg_extension e ON e.oid = d.refobjid
                        WHERE d.objid = p.oid AND d.deptype = 'e'
                      )
                    """
                ),
                {"schemas": list(schemas)},
            )
        )
    )

    return CatalogInventory(
        alembic_revision=revision,
        extensions=extensions,
        schemas=schemas,
        relations=relations,
        columns=columns,
        constraints=constraints,
        indexes=indexes,
        enums=enums_t,
        triggers=triggers,
        routines=routines,
    )


def collect_inventory_from_engine(engine: Engine) -> CatalogInventory:
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        return collect_inventory(connection)


def is_empty_inventory(inventory: CatalogInventory) -> bool:
    if inventory.alembic_revision is not None:
        return False
    if inventory.relations:
        return False
    if inventory.columns or inventory.constraints or inventory.indexes:
        return False
    if inventory.enums or inventory.triggers or inventory.routines:
        return False
    if set(inventory.schemas) - {"public"}:
        return False
    if set(inventory.extensions) - ALLOWED_EXTENSIONS:
        return False
    return True


def classify_inventory(
    inventory: CatalogInventory,
    *,
    policy: Policy,
    expected: CatalogInventory | None = None,
    supported_head: str | None = None,
    known_revisions: frozenset[str] | None = None,
) -> CompatibilityVerdict:
    """Classify live inventory for migrate or startup policy."""
    supported_head = supported_head or _supported_head()
    try:
        snapshot = expected if expected is not None else load_expected_snapshot(supported_head)
    except FileNotFoundError:
        return CompatibilityVerdict(REASON_SNAPSHOT_HEAD_MISMATCH, False)
    except ValueError:
        return CompatibilityVerdict(REASON_SNAPSHOT_HEAD_MISMATCH, False)

    snapshot_meta_path = snapshot_path_for_head(supported_head)
    if snapshot_meta_path.is_file():
        meta = json.loads(snapshot_meta_path.read_text(encoding="utf-8")).get("alembic_head")
        if meta != supported_head:
            return CompatibilityVerdict(REASON_SNAPSHOT_HEAD_MISMATCH, False)

    if set(inventory.extensions) - ALLOWED_EXTENSIONS:
        return CompatibilityVerdict(REASON_EXTENSION, False)

    if is_empty_inventory(inventory):
        if policy == "migrate":
            return CompatibilityVerdict(REASON_EMPTY_OK, True)
        return CompatibilityVerdict(REASON_PARTIAL, False)

    revision = inventory.alembic_revision
    if revision is None:
        return CompatibilityVerdict(REASON_PARTIAL, False)

    if known_revisions is not None and revision not in known_revisions:
        return CompatibilityVerdict(REASON_UNKNOWN_HISTORY, False)

    if revision != supported_head:
        if known_revisions is not None and revision in known_revisions:
            # Order unknown without full graph: treat unequal known as behind unless
            # caller marks ahead via known_revisions ordering helper.
            return CompatibilityVerdict(
                _revision_direction(revision, supported_head, known_revisions),
                False,
            )
        return CompatibilityVerdict(REASON_UNKNOWN_HISTORY, False)

    # Exact head — require catalog match.
    if _catalog_equals(inventory, snapshot):
        return CompatibilityVerdict(REASON_CURRENT_TARGET_OK, True)

    return _classify_catalog_mismatch(inventory, snapshot)


def reconcile(
    engine: Engine,
    *,
    policy: Policy,
    supported_head: str | None = None,
    known_revisions: frozenset[str] | None = None,
) -> tuple[CatalogInventory, CompatibilityVerdict]:
    inventory = collect_inventory_from_engine(engine)
    verdict = classify_inventory(
        inventory,
        policy=policy,
        supported_head=supported_head or _supported_head(),
        known_revisions=known_revisions,
    )
    return inventory, verdict


def _classify_catalog_mismatch(
    live: CatalogInventory,
    expected: CatalogInventory,
) -> CompatibilityVerdict:
    live_rel = {name for _schema, name, _kind in live.relations}
    expected_rel = {name for _schema, name, _kind in expected.relations}
    extra = live_rel - expected_rel
    missing = expected_rel - live_rel

    if extra & DEFERRED_WIKI_TABLES:
        return CompatibilityVerdict(REASON_LEGACY, False)

    live_cols = {(table, column) for _schema, table, column, _type in live.columns}
    if live_cols & DEFERRED_WIKI_COLUMNS:
        return CompatibilityVerdict(REASON_LEGACY, False)

    if len(extra) == 1 and len(missing) == 1:
        return CompatibilityVerdict(REASON_RENAMED, False)
    if extra and not missing:
        return CompatibilityVerdict(REASON_UNKNOWN_OBJECT, False)
    if missing and not extra:
        return CompatibilityVerdict(REASON_PARTIAL, False)
    if extra or missing:
        return CompatibilityVerdict(REASON_CATALOG_MISMATCH, False)
    return CompatibilityVerdict(REASON_CATALOG_MISMATCH, False)


def _catalog_equals(live: CatalogInventory, expected: CatalogInventory) -> bool:
    return (
        live.extensions == expected.extensions
        and live.schemas == expected.schemas
        and live.relations == expected.relations
        and live.columns == expected.columns
        and live.constraints == expected.constraints
        and live.indexes == expected.indexes
        and live.enums == expected.enums
        and live.triggers == expected.triggers
        and live.routines == expected.routines
    )


def _revision_direction(
    revision: str,
    supported_head: str,
    known_revisions: frozenset[str],
) -> str:
    """Best-effort behind/ahead without requiring a full Alembic ScriptDirectory.

    Callers that have ordered history should pass known_revisions and use
    classify_with_script_directory instead. Here: unequal known → behind by default
    unless revision is not a prefix ancestor — still closed as behind/ahead via
    optional ordered list stored as comma? Keep simple: unknown relative → behind
    when both known (safe refuse); use REASON_AHEAD only when caller supplies
    ordered_heads where revision index > head index.
    """
    del known_revisions, supported_head, revision
    return REASON_BEHIND


def classify_with_ordered_revisions(
    inventory: CatalogInventory,
    *,
    policy: Policy,
    ordered_revisions: tuple[str, ...],
    supported_head: str | None = None,
    expected: CatalogInventory | None = None,
) -> CompatibilityVerdict:
    supported_head = supported_head or _supported_head()
    known = frozenset(ordered_revisions)
    base = classify_inventory(
        inventory,
        policy=policy,
        expected=expected,
        supported_head=supported_head,
        known_revisions=known,
    )
    if base.reason not in {REASON_BEHIND, REASON_UNKNOWN_HISTORY}:
        return base
    revision = inventory.alembic_revision
    if revision is None or revision not in known or supported_head not in known:
        return base
    if revision == supported_head:
        return base
    rev_idx = ordered_revisions.index(revision)
    head_idx = ordered_revisions.index(supported_head)
    if rev_idx < head_idx:
        return CompatibilityVerdict(REASON_BEHIND, False)
    if rev_idx > head_idx:
        return CompatibilityVerdict(REASON_AHEAD, False)
    return base


def _alembic_revision(connection: Connection) -> str | None:
    exists = connection.scalar(
        text(
            """
            SELECT EXISTS (
              SELECT 1
              FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
              WHERE n.nspname = 'public' AND c.relname = 'alembic_version' AND c.relkind = 'r'
            )
            """
        )
    )
    if not exists:
        return None
    rows = list(connection.execute(text("SELECT version_num FROM alembic_version")))
    if not rows:
        return None
    if len(rows) != 1:
        return "__multiple_alembic_version_rows__"
    return str(rows[0][0])


def _inventory_to_dict(inventory: CatalogInventory) -> dict[str, Any]:
    data = asdict(inventory)
    # tuples → lists for JSON
    return {
        "alembic_revision": data["alembic_revision"],
        "extensions": [list(item) for item in data["extensions"]],
        "schemas": list(data["schemas"]),
        "relations": [list(item) for item in data["relations"]],
        "columns": [list(item) for item in data["columns"]],
        "constraints": [list(item) for item in data["constraints"]],
        "indexes": [list(item) for item in data["indexes"]],
        "enums": [[s, n, list(labels)] for s, n, labels in data["enums"]],
        "triggers": [list(item) for item in data["triggers"]],
        "routines": [list(item) for item in data["routines"]],
    }


def _inventory_from_dict(raw: dict[str, Any]) -> CatalogInventory:
    return CatalogInventory(
        alembic_revision=raw.get("alembic_revision"),
        extensions=tuple(tuple(item) for item in raw.get("extensions", [])),
        schemas=tuple(raw.get("schemas", [])),
        relations=tuple(tuple(item) for item in raw.get("relations", [])),
        columns=tuple(tuple(item) for item in raw.get("columns", [])),
        constraints=tuple(tuple(item) for item in raw.get("constraints", [])),
        indexes=tuple(tuple(item) for item in raw.get("indexes", [])),
        enums=tuple((s, n, tuple(labels)) for s, n, labels in raw.get("enums", [])),
        triggers=tuple(tuple(item) for item in raw.get("triggers", [])),
        routines=tuple(tuple(item) for item in raw.get("routines", [])),
    )


def inventory_from_parts(
    *,
    alembic_revision: str | None = None,
    extensions: tuple[tuple[str, str], ...] = (("plpgsql", "1.0"),),
    schemas: tuple[str, ...] = ("public",),
    relations: tuple[tuple[str, str, str], ...] = (),
    columns: tuple[tuple[str, str, str, str], ...] = (),
    constraints: tuple[tuple[str, str, str, str], ...] = (),
    indexes: tuple[tuple[str, str, str, str], ...] = (),
    enums: tuple[tuple[str, str, tuple[str, ...]], ...] = (),
    triggers: tuple[tuple[str, str, str], ...] = (),
    routines: tuple[tuple[str, str, str], ...] = (),
) -> CatalogInventory:
    """Test helper to build inventories without a live database."""
    return CatalogInventory(
        alembic_revision=alembic_revision,
        extensions=tuple(sorted(extensions)),
        schemas=tuple(sorted(schemas)),
        relations=tuple(sorted(relations)),
        columns=tuple(sorted(columns)),
        constraints=tuple(sorted(constraints)),
        indexes=tuple(sorted(indexes)),
        enums=tuple(sorted(enums, key=lambda item: (item[0], item[1]))),
        triggers=tuple(sorted(triggers)),
        routines=tuple(sorted(routines)),
    )
