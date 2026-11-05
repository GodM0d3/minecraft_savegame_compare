
#!/usr/bin/env python3
"""Vergleicht zwei Minecraft-Welten auf Dateiebene."""

import argparse
import csv
import hashlib
from pathlib import Path


def sha256(path: Path) -> str:
    """Berechnet SHA-256, ohne die gesamte Datei in RAM zu laden."""
    digest = hashlib.sha256()

    with path.open("rb") as file:
        while chunk := file.read(4 * 1024 * 1024):
            digest.update(chunk)

    return digest.hexdigest()


def collect_files(root: Path) -> dict[str, Path]:
    """Erfasst alle Dateien mit relativem Pfad als Schlüssel."""
    return {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file()
    }


def compare(backup: Path, current: Path, output: Path):
    backup = backup.resolve()
    current = current.resolve()
    output = output.resolve()

    if not backup.is_dir() or not current.is_dir():
        raise ValueError("Beide Weltverzeichnisse müssen existieren.")

    if backup == current:
        raise ValueError("Backup und aktuelle Welt sind identische Pfade.")

    if backup in output.parents or current in output.parents:
        raise ValueError("Ausgabe darf nicht innerhalb der Welten liegen.")

    if output == backup or output == current:
        raise ValueError("Ausgabe darf keine der Welten sein.")

    output.mkdir(parents=True, exist_ok=True)

    print("Erfasse Dateien ...")
    old_files = collect_files(backup)
    new_files = collect_files(current)

    print(f"Backup:  {len(old_files)} Dateien")
    print(f"Aktuell: {len(new_files)} Dateien")

    all_paths = sorted(set(old_files) | set(new_files))

    results = {
        "only_backup": [],
        "only_current": [],
        "different": [],
        "identical": [],
        "empty_backup": [],
        "empty_new": [],
        "both_empty": [],
        "size_shrunk": []
    }
    errors = []
    total = len(all_paths)
    ignore_list = {
        "data/minecraft/maps/",
        "datapacks/",
        "data/minecraft/game_rules.dat",
        "data/durability_ping/command_storage.dat",
        "data/minecraft/weather.dat",
        "data/minecraft/scheduled_events.dat",
        "dimensions/minecraft/overworld/region/",
        "dimensions/minecraft/the_end/region/",
        "dimensions/minecraft/the_nether/region/",
        "icon.png",
        "xaeromap.txt",
        "dimensions/minecraft/overworld/entities/",
        "dimensions/minecraft/the_end/entities/",
        "dimensions/minecraft/the_nether/entities/",
        "dimensions/minecraft/overworld/poi/",
        "dimensions/minecraft/the_end/poi/",
        "dimensions/minecraft/the_nether/poi/",
        "data/fabric/registry_entries.dat",
        "level.dat",
        "level.dat_old",
        "players/data/3c2c2301-0256-4098-aa8a-0f170a5b0b7e.dat",
        "players/data/3c2c2301-0256-4098-aa8a-0f170a5b0b7e.dat_old",
        "dimensions/minecraft/overworld/data/minecraft/raids.dat",
        "dimensions/minecraft/the_end/data/minecraft/raids.dat",
        "dimensions/minecraft/the_nether/data/minecraft/raids.dat",
        "data/minecraft/random_sequences.dat",
        #Maybe damaged
        "data/minecraft/world_clocks.dat", # zeit zurückgesetzt
        "data/minecraft/wandering_trader.dat", #missing spawn chance
        #Datenverlust, backup file 1 zu 1 übernehmen:
        "data/minecraft/scoreboard.dat",
        "players/stats/3c2c2301-0256-4098-aa8a-0f170a5b0b7e.json",
        "players/advancements/3c2c2301-0256-4098-aa8a-0f170a5b0b7e.json",
    }

    for index, relative_path in enumerate(all_paths, 1):
        if any(relative_path.startswith(item) for item in ignore_list):
            continue

        old = old_files.get(relative_path)
        new = new_files.get(relative_path)

        try:
            old_size = old.stat().st_size if old else None
            new_size = new.stat().st_size if new else None
            
            if old is None:
                category = "only_current"

            elif new is None:
                category = "only_backup"

            elif old_size == 0 and new_size == 0:
                category = "both_empty"

            elif old_size == 0:
                category = "empty_backup"

            elif new_size == 0:
                category = "empty_new"

            elif old_size != new_size:
                category = "different"
                if old_size > new_size:
                    category = "size_shrunk"

            elif sha256(old) != sha256(new):
                category = "different"

            else:
                category = "identical"

            results[category].append({
                "path": relative_path,
                "backup_size": old_size,
                "current_size": new_size,
            })

        except OSError as error:
            errors.append((relative_path, str(error)))

        if index % 100 == 0 or index == total:
            print(
                f"\r[{index}/{total}] "
                f"{index / total * 100:.1f}%",
                end="",
                flush=True,
            )

    print("\n\nErgebnis:")

    for category, entries in results.items():
        filename = output / f"{category}.csv"

        if not entries:
            filename.unlink(missing_ok=True)
            print(f"  {category:15}: 0")
            continue

        with filename.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=["path", "backup_size", "current_size"],
                delimiter=";"
            )
            writer.writeheader()
            writer.writerows(entries)

        print(f"  {category:15}: {len(entries)}")
    """for category, entries in results.items():
        filename = output / f"{category}.csv"

        with filename.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=["path", "backup_size", "current_size"],
                delimiter=";"
            )
            writer.writeheader()
            writer.writerows(entries)

        print(f"  {category:15}: {len(entries)}")
"""
    with (output / "errors.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as file:
        writer = csv.writer(file, delimiter=";")
        writer.writerow(["path", "error"])
        writer.writerows(errors)

    print(f"  errors         : {len(errors)}")
    print(f"\nBerichte gespeichert in: {output}")


def main():
    parser = argparse.ArgumentParser(
        description="Vergleicht zwei Minecraft-Welten."
    )

    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("comparison"))

    args = parser.parse_args()
    compare(args.backup, args.current, args.output)


if __name__ == "__main__":
    main()
