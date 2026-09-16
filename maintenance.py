"""Back up SQLite and local assets; migrate existing SQLite/PostgreSQL safely."""
import argparse
from contextlib import closing
import hashlib
import json
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from platform_app.config import Config, DEFAULT_SQLITE_DB_PATH


ROOT = Path(__file__).resolve().parent
VALID_GROUP = "((guest_type = 'single' AND party_size = 1) OR (guest_type = 'couple' AND party_size = 2) OR (guest_type = 'family' AND party_size BETWEEN 2 AND 100))"


def sqlite_copy(source, target):
    source, target = Path(source).resolve(), Path(target).resolve()
    if not source.is_file() or target.exists():
        raise ValueError("Source absente ou destination existante.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as src:
        with closing(sqlite3.connect(target)) as dst:
            src.backup(dst)
            if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("Échec du contrôle SQLite.")


def verify_backup(folder):
    folder = Path(folder).resolve()
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    for relative, expected in manifest.items():
        path = (folder / relative).resolve()
        if not path.is_relative_to(folder) or not path.is_file():
            raise ValueError("Fichier de sauvegarde absent ou chemin invalide.")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Empreinte de sauvegarde incorrecte.")
        if path.suffix == ".db":
            # Rehearse restoring each database into a separate scratch directory.
            with tempfile.TemporaryDirectory() as tmp:
                sqlite_copy(path, Path(tmp) / "restored.db")
    return len(manifest)


def backup(destination=None):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    folder = Path(destination or ROOT / "backups" / stamp).resolve()
    folder.mkdir(parents=True, exist_ok=False)
    sources = [Path(DEFAULT_SQLITE_DB_PATH)]
    sources += list((ROOT / "backups_db_obsoletes").glob("*.db"))
    for source in sources:
        if source.is_file():
            sqlite_copy(source, folder / source.relative_to(ROOT))
    if (ROOT / "storage").is_dir():
        shutil.copytree(ROOT / "storage", folder / "storage", ignore=shutil.ignore_patterns("tmp"))
    manifest = {str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in folder.rglob("*") if p.is_file()}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    verify_backup(folder)
    return folder


def migrate(engine, apply=False):
    """No data correction by guesswork: invalid legacy rows block the migration."""
    with engine.begin() as connection:
        tables = inspect(connection).get_table_names()
        if not {"guest", "invitation"}.issubset(tables):
            raise ValueError("Initialisez les tables avant la migration.")
        invalid = connection.execute(text(
            f"SELECT count(*) FROM guest WHERE guest_type IS NULL OR party_size IS NULL OR NOT {VALID_GROUP}"
        )).scalar_one()
        duplicates = connection.execute(text(
            "SELECT count(*) FROM (SELECT guest_id FROM invitation GROUP BY guest_id HAVING count(*) > 1) AS duplicates"
        )).scalar_one()
        summary = {"invalid_groups": invalid, "duplicate_invitations": duplicates}
        if not apply:
            return summary
        if invalid or duplicates:
            raise ValueError("Migration refusée : corriger les anomalies après inventaire, sans supprimer les invitations.")
        dialect = connection.dialect.name
        if dialect not in {"sqlite", "postgresql"}:
            raise ValueError("Base non prise en charge.")
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_invitation_guest ON invitation (guest_id)"))
        if dialect == "sqlite":
            # SQLite cannot add CHECK without rebuilding the table. Triggers enforce
            # the same rules without losing unknown legacy columns or relationships.
            predicate = VALID_GROUP.replace("guest_type", "NEW.guest_type").replace("party_size", "NEW.party_size")
            for operation in ("INSERT", "UPDATE"):
                connection.execute(text(
                    f"CREATE TRIGGER IF NOT EXISTS guest_size_{operation.lower()} BEFORE {operation} ON guest "
                    f"WHEN NEW.guest_type IS NULL OR NEW.party_size IS NULL OR NOT {predicate} "
                    "BEGIN SELECT RAISE(ABORT, 'Invalid guest group size'); END"
                ))
        else:
            names = {c["name"] for c in inspect(connection).get_check_constraints("guest")}
            if "ck_guest_type_size" not in names:
                connection.execute(text(f"ALTER TABLE guest ADD CONSTRAINT ck_guest_type_size CHECK ({VALID_GROUP})"))
        connection.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (version VARCHAR(80) PRIMARY KEY)"))
        connection.execute(text("INSERT INTO schema_migrations (version) VALUES ('001_stabilisation') ON CONFLICT (version) DO NOTHING"))
        return {**summary, "applied": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("backup")
    verify = commands.add_parser("verify-backup")
    verify.add_argument("folder")
    migration = commands.add_parser("migrate")
    migration.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.command == "backup":
        print("Sauvegarde locale vérifiée :", backup())
    elif args.command == "verify-backup":
        print("Fichiers vérifiés :", verify_backup(args.folder))
    else:
        engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
        try:
            print(migrate(engine, args.apply))
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
