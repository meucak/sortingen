#!/usr/bin/env python3
"""
sortingen — Akıllı Dosya Türü & Klasör Düzenleyici (Smart Directory Sorter CLI)

Kullanım Örnekleri:
  sortingen indirilenler --doctype
  sortingen ~/İndirilenler --doctype
  sortingen /path/to/dir --doctype
  sortingen /path/to/dir --category
  sortingen /path/to/dir --date
  sortingen /path/to/dir --doctype --dry-run
  sortingen /path/to/dir --undo
  echo ~/İndirilenler | sortingen --doctype
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

VERSION = "1.1.0"

# Active download / temporary extensions that must never be interrupted
PARTIAL_EXTENSIONS = {
    ".crdownload",
    ".part",
    ".partial",
    ".tmp",
    ".download",
    ".opdownload",
    ".aria2",
}

# System desktop icons preserved when --include-desktop is enabled
SYSTEM_DESKTOP_FILES = {
    "computer.desktop",
    "trash-can.desktop",
    "user-home.desktop",
    "network.desktop",
}

DESKTOP_DIR_NAMES = {"desktop", "masaustu"}

# Compound multi-dot extensions preserved as a single doctype
COMPOUND_EXTENSIONS = (
    ".tar.gz",
    ".tar.xz",
    ".tar.bz2",
    ".tar.zst",
    ".tar.lz",
)

# High-level categories for --category mode
CATEGORY_MAP: Dict[str, str] = {
    # Belgeler
    "pdf": "Belgeler",
    "doc": "Belgeler",
    "docx": "Belgeler",
    "odt": "Belgeler",
    "rtf": "Belgeler",
    "txt": "Belgeler",
    "md": "Belgeler",
    "xls": "Belgeler",
    "xlsx": "Belgeler",
    "ods": "Belgeler",
    "csv": "Belgeler",
    "ppt": "Belgeler",
    "pptx": "Belgeler",
    "odp": "Belgeler",
    "epub": "Belgeler",
    "log": "Belgeler",
    # Resimler
    "jpg": "Resimler",
    "jpeg": "Resimler",
    "png": "Resimler",
    "gif": "Resimler",
    "webp": "Resimler",
    "svg": "Resimler",
    "bmp": "Resimler",
    "ico": "Resimler",
    "heic": "Resimler",
    "tiff": "Resimler",
    # Videolar
    "mp4": "Videolar",
    "mkv": "Videolar",
    "webm": "Videolar",
    "avi": "Videolar",
    "mov": "Videolar",
    "flv": "Videolar",
    "wmv": "Videolar",
    # Müzik
    "mp3": "Müzik",
    "wav": "Müzik",
    "flac": "Müzik",
    "ogg": "Müzik",
    "m4a": "Müzik",
    "aac": "Müzik",
    "opus": "Müzik",
    # Arşivler
    "zip": "Arşivler",
    "rar": "Arşivler",
    "7z": "Arşivler",
    "tar": "Arşivler",
    "gz": "Arşivler",
    "xz": "Arşivler",
    "bz2": "Arşivler",
    "zst": "Arşivler",
    "tar.gz": "Arşivler",
    "tar.xz": "Arşivler",
    "tar.bz2": "Arşivler",
    "tar.zst": "Arşivler",
    "tar.lz": "Arşivler",
    "iso": "Arşivler",
    "img": "Arşivler",
    # Uygulamalar / Kurulumlar / Betikler / Kısayollar
    "apk": "apps",
    "deb": "apps",
    "rpm": "apps",
    "exe": "apps",
    "msi": "apps",
    "dmg": "apps",
    "appimage": "apps",
    "desktop": "apps",
    "sh": "apps",
    "py": "apps",
    "bin": "apps",
    "run": "apps",
    "flatpakref": "apps",
    # Kodlar
    "js": "Kodlar",
    "ts": "Kodlar",
    "html": "Kodlar",
    "css": "Kodlar",
    "json": "Kodlar",
    "yaml": "Kodlar",
    "yml": "Kodlar",
    "xml": "Kodlar",
    "sql": "Kodlar",
    "c": "Kodlar",
    "cpp": "Kodlar",
    "rs": "Kodlar",
    "go": "Kodlar",
    "java": "Kodlar",
}

CATEGORY_ALIASES: Dict[str, List[str]] = {
    "Resimler": ["Resimler", "Pictures", "Görseller"],
    "Videolar": ["Videolar", "Videos"],
    "Müzik": ["Müzik", "Muzik", "Music", "Musics", "Sesler"],
    "Belgeler": ["Belgeler", "Documents"],
    "apps": ["apps", "Apps", "Uygulamalar", "Kurulumlar"],
    "Arşivler": ["Arşivler", "Arsivler", "Archives"],
}

WELL_KNOWN_ALIASES: Dict[str, List[str]] = {
    "indirilenler": ["İndirilenler", "Indirilenler", "Downloads", "downloads"],
    "downloads": ["Downloads", "İndirilenler", "Indirilenler", "downloads"],
    "belgeler": ["Belgeler", "Documents", "belgeler", "documents"],
    "documents": ["Documents", "Belgeler", "documents", "belgeler"],
    "masaustu": ["Masaüstü", "Masaustu", "Desktop", "desktop"],
    "desktop": ["Desktop", "Masaüstü", "Masaustu", "desktop"],
    "resimler": ["Resimler", "Pictures", "resimler", "pictures"],
    "pictures": ["Pictures", "Resimler", "pictures", "resimler"],
    "videolar": ["Videolar", "Videos", "videolar", "videos"],
    "muzik": ["Müzik", "Muzik", "Music", "music"],
}


def normalize_tr(text: str) -> str:
    """Fold Turkish and ASCII characters into a canonical lowercase key for matching."""
    table = str.maketrans(
        {
            "İ": "i",
            "I": "i",
            "ı": "i",
            "i": "i",
            "Ş": "s",
            "ş": "s",
            "Ğ": "g",
            "ğ": "g",
            "Ü": "u",
            "ü": "u",
            "Ö": "o",
            "ö": "o",
            "Ç": "c",
            "ç": "c",
        }
    )
    return text.translate(table).casefold().strip()


def default_history_path() -> Path:
    cache_dir = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "sortingen"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "history.json"


def resolve_target_dir(
    raw_target: str,
    cwd: Optional[Path] = None,
    home: Optional[Path] = None,
) -> Path:
    """
    Resolve a directory path intelligently:
    1. Exact path (absolute, ~ expanded, or relative to cwd)
    2. Case-insensitive / Turkish-normalized subdirectory match in cwd
    3. Well-known folder alias or Turkish-normalized match in $HOME (e.g. 'indirilenler' -> '~/İndirilenler')
    """
    cwd = (cwd or Path.cwd()).resolve()
    home = (home or Path.home()).resolve()

    cleaned = raw_target.strip().strip("|").strip()
    if not cleaned:
        return cwd

    expanded = Path(os.path.expanduser(cleaned))
    if expanded.is_absolute():
        if expanded.is_dir():
            return expanded.resolve()
        raise FileNotFoundError(f"Klasör bulunamadı: {expanded}")

    # 1. Exact relative to cwd
    direct = cwd / expanded
    if direct.is_dir():
        return direct.resolve()

    norm_query = normalize_tr(cleaned)

    # 2. Case/Turkish-insensitive match in cwd
    if "/" not in cleaned and "\\" not in cleaned:
        for child in cwd.iterdir():
            if child.is_dir() and normalize_tr(child.name) == norm_query:
                return child.resolve()

        # 3. Check $HOME direct children with Turkish normalization
        if home.is_dir():
            for child in home.iterdir():
                if child.is_dir() and normalize_tr(child.name) == norm_query:
                    return child.resolve()

            # 4. Check well-known aliases (e.g. 'indirilenler' <-> 'Downloads')
            for alias_name in WELL_KNOWN_ALIASES.get(norm_query, []):
                candidate = home / alias_name
                if candidate.is_dir():
                    return candidate.resolve()

    raise FileNotFoundError(
        f"Hedef klasör bulunamadı: '{raw_target}' (Aranan dizinler: {cwd}, {home})"
    )


def extract_doctype(filename: str) -> str:
    """
    Extract normalized lowercase doctype extension from filename.
    Preserves compound archive extensions like 'tar.gz', returns 'diger' if no extension.
    """
    lower = filename.lower()
    for comp in COMPOUND_EXTENSIONS:
        if lower.endswith(comp) and len(lower) > len(comp):
            return comp.lstrip(".")

    ext = Path(filename).suffix.lower().lstrip(".")
    return ext if ext else "diger"


def is_partial_download(filename: str) -> bool:
    lower = filename.lower()
    return any(lower.endswith(ext) for ext in PARTIAL_EXTENSIONS)


def resolve_desktop_dir(home: Optional[Path] = None) -> Optional[Path]:
    """Locate the user's Desktop directory (XDG config, ~/Desktop, or ~/Masaüstü)."""
    base_home = (home or Path.home()).resolve()

    if home is None:
        xdg_desktop = os.environ.get("XDG_DESKTOP_DIR")
        if xdg_desktop:
            p = Path(os.path.expanduser(xdg_desktop)).resolve()
            if p.is_dir():
                return p
        user_dirs_file = base_home / ".config" / "user-dirs.dirs"
        if user_dirs_file.is_file():
            try:
                for line in user_dirs_file.read_text(
                    encoding="utf-8", errors="ignore"
                ).splitlines():
                    line = line.strip()
                    if line.startswith("XDG_DESKTOP_DIR="):
                        raw_val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        expanded = raw_val.replace("$HOME", str(base_home))
                        p = Path(os.path.expanduser(expanded)).resolve()
                        if p.is_dir():
                            return p
            except OSError:
                pass

    for name in ("Desktop", "Masaüstü", "Masaustu", "desktop"):
        candidate = base_home / name
        if candidate.is_dir():
            return candidate.resolve()

    return None


def find_or_plan_dest_folder(
    target_dir: Path,
    folder_key: str,
    existing_dirs_map: Dict[str, Path],
    mode: str = "doctype",
    existing_dirs_tr_map: Optional[Dict[str, Path]] = None,
) -> Tuple[Path, bool]:
    """
    Check if a matching folder already exists in target_dir (case-insensitively and
    via category aliases when mode == 'category').
    Returns (folder_path, will_be_newly_created).
    """
    candidates = (
        CATEGORY_ALIASES.get(folder_key, [folder_key])
        if mode == "category"
        else [folder_key]
    )

    for alias in candidates:
        lookup = alias.casefold()
        if lookup in existing_dirs_map:
            matched = existing_dirs_map[lookup]
            if (
                mode == "doctype"
                and folder_key == "desktop"
                and normalize_tr(matched.name) in DESKTOP_DIR_NAMES
                and matched.name != "desktop"
            ):
                continue
            return matched, False

    if existing_dirs_tr_map:
        for alias in candidates:
            tr_lookup = normalize_tr(alias)
            if tr_lookup in existing_dirs_tr_map:
                matched = existing_dirs_tr_map[tr_lookup]
                if (
                    mode == "doctype"
                    and folder_key == "desktop"
                    and normalize_tr(matched.name) in DESKTOP_DIR_NAMES
                    and matched.name != "desktop"
                ):
                    continue
                return matched, False

    return target_dir / folder_key, True


def compute_safe_destination(dest_dir: Path, filename: str, reserved_paths: set) -> Path:
    """
    Ensure zero overwrites. If dest_dir/filename exists or is already planned in reserved_paths,
    append ' (1)', ' (2)', etc. before the extension.
    """
    candidate = dest_dir / filename
    if not candidate.exists() and candidate not in reserved_paths:
        return candidate

    lower = filename.lower()
    stem = filename
    suffix = ""
    matched_compound = False
    for comp in COMPOUND_EXTENSIONS:
        if lower.endswith(comp) and len(lower) > len(comp):
            stem = filename[: -len(comp)]
            suffix = filename[-len(comp) :]
            matched_compound = True
            break

    if not matched_compound:
        p = Path(filename)
        stem = p.stem
        suffix = p.suffix

    counter = 1
    while True:
        alt_name = f"{stem} ({counter}){suffix}"
        alt_path = dest_dir / alt_name
        if not alt_path.exists() and alt_path not in reserved_paths:
            return alt_path
        counter += 1


def sort_directory(
    target_dir: Path | str,
    mode: str = "doctype",
    include_hidden: bool = False,
    dry_run: bool = False,
    history_path: Optional[Path] = None,
    include_desktop: bool = False,
    desktop_dir: Optional[Path | str] = None,
) -> dict:
    """
    Sort top-level files inside `target_dir` into subdirectories according to `mode`:
      - 'doctype': By file extension (pdf/, docx/, jpg/, ...), reusing existing folders case-insensitively.
      - 'category': By semantic group (Belgeler/, Resimler/, Videolar/, Müzik/, apps/, Arşivler/, ...).
      - 'date': By file modification YYYY-MM.
    When `include_desktop` is True, files from Desktop/Masaüstü (excluding system icons) are also included.
    """
    target = Path(target_dir).resolve()
    if not target.is_dir():
        raise NotADirectoryError(f"Geçerli bir klasör değil: {target}")

    history_file = history_path or default_history_path()

    resolved_desktop: Optional[Path] = None
    if desktop_dir is not None:
        cand = Path(desktop_dir).resolve()
        if cand.is_dir():
            resolved_desktop = cand
    elif include_desktop:
        if target != Path.home().resolve():
            resolved_desktop = resolve_desktop_dir(home=target)
        if resolved_desktop is None:
            resolved_desktop = resolve_desktop_dir()

    # Map existing immediate subdirectories case-insensitively and Turkish-normalized
    existing_dirs_map: Dict[str, Path] = {}
    existing_dirs_tr_map: Dict[str, Path] = {}
    existing_subdirs: List[Path] = []
    for entry in sorted(target.iterdir(), key=lambda p: p.name):
        if entry.is_dir():
            existing_subdirs.append(entry)
            key = entry.name.casefold()
            if key not in existing_dirs_map:
                existing_dirs_map[key] = entry
            tr_key = normalize_tr(entry.name)
            if tr_key not in existing_dirs_tr_map:
                existing_dirs_tr_map[tr_key] = entry

    has_desktop_dir = any(
        (normalize_tr(entry.name) in DESKTOP_DIR_NAMES and entry.name != "desktop")
        or (resolved_desktop is not None and entry.resolve() == resolved_desktop)
        for entry in existing_subdirs
    )

    moves: List[dict] = []
    created_dirs: List[str] = []
    created_dirs_set: set = set()
    reserved_destinations: set = set()
    skipped_hidden = 0
    skipped_partial = 0
    skipped_system_desktop = 0
    desktop_included_count = 0
    groups_summary: Dict[str, dict] = {}

    scan_sources: List[Tuple[Path, bool]] = [
        (target, resolved_desktop is not None and target == resolved_desktop)
    ]
    if (
        include_desktop
        and resolved_desktop is not None
        and resolved_desktop.is_dir()
        and resolved_desktop != target
    ):
        scan_sources.append((resolved_desktop, True))

    entries: List[Tuple[Path, bool]] = []
    for src_dir, is_desktop_src in scan_sources:
        dir_files = sorted(
            [e for e in src_dir.iterdir() if e.is_file() and not e.is_symlink()],
            key=lambda e: e.name.lower(),
        )
        for f in dir_files:
            entries.append((f, is_desktop_src))

    for file_path, is_desktop_src in entries:
        fname = file_path.name

        if fname.startswith(".") and not include_hidden:
            skipped_hidden += 1
            continue

        if is_desktop_src and fname.casefold() in SYSTEM_DESKTOP_FILES:
            skipped_system_desktop += 1
            continue

        if is_partial_download(fname):
            skipped_partial += 1
            continue

        ext = extract_doctype(fname)
        if mode == "doctype":
            folder_key = ext
            if folder_key == "desktop" and has_desktop_dir:
                apps_match = next(
                    (
                        existing_dirs_map.get(a.casefold())
                        or existing_dirs_tr_map.get(normalize_tr(a))
                        for a in CATEGORY_ALIASES["apps"]
                        if a.casefold() in existing_dirs_map
                        or normalize_tr(a) in existing_dirs_tr_map
                    ),
                    None,
                )
                folder_key = (
                    apps_match.name if apps_match is not None else "desktop_shortcuts"
                )
        elif mode == "category":
            folder_key = CATEGORY_MAP.get(ext, "Diğer")
        elif mode == "date":
            mtime = file_path.stat().st_mtime
            dt = datetime.datetime.fromtimestamp(mtime)
            folder_key = dt.strftime("%Y-%m")
        else:
            raise ValueError(f"Bilinmeyen sıralama modu: {mode}")

        dest_folder, is_new_folder = find_or_plan_dest_folder(
            target,
            folder_key,
            existing_dirs_map,
            mode=mode,
            existing_dirs_tr_map=existing_dirs_tr_map,
        )

        if is_new_folder and str(dest_folder) not in created_dirs_set:
            if not dest_folder.is_dir():
                created_dirs.append(str(dest_folder))
                created_dirs_set.add(str(dest_folder))
            existing_dirs_map[dest_folder.name.casefold()] = dest_folder
            existing_dirs_tr_map[normalize_tr(dest_folder.name)] = dest_folder
            existing_dirs_map.setdefault(folder_key.casefold(), dest_folder)
            existing_dirs_tr_map.setdefault(normalize_tr(folder_key), dest_folder)

        safe_dest = compute_safe_destination(dest_folder, fname, reserved_destinations)
        reserved_destinations.add(safe_dest)

        if is_desktop_src:
            desktop_included_count += 1

        folder_label = dest_folder.name
        if folder_label not in groups_summary:
            groups_summary[folder_label] = {
                "count": 0,
                "newly_created": str(dest_folder) in created_dirs_set,
                "files": [],
            }
        groups_summary[folder_label]["count"] += 1
        groups_summary[folder_label]["files"].append(
            {"from": fname, "to": safe_dest.name}
        )

        moves.append(
            {
                "src": str(file_path),
                "dst": str(safe_dest),
                "folder": folder_label,
            }
        )

    if not dry_run and moves:
        staged_map: Dict[str, Path] = {}
        for idx, m in enumerate(moves):
            if m["src"] in created_dirs_set:
                src_p = Path(m["src"])
                tmp_p = src_p.with_name(f".sortingen_stage_{os.getpid()}_{idx}_{src_p.name}")
                shutil.move(str(src_p), str(tmp_p))
                staged_map[m["src"]] = tmp_p

        for d_str in created_dirs:
            Path(d_str).mkdir(parents=True, exist_ok=True)

        executed_moves = []
        for m in moves:
            actual_src = staged_map.get(m["src"], Path(m["src"]))
            dst_p = Path(m["dst"])
            dst_p.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(actual_src), str(dst_p))
            executed_moves.append(m)

        record_history(
            history_file=history_file,
            target_dir=str(target),
            mode=mode,
            moves=executed_moves,
            created_dirs=created_dirs,
        )

    return {
        "target_dir": str(target),
        "mode": mode,
        "dry_run": dry_run,
        "include_desktop": include_desktop,
        "desktop_dir": str(resolved_desktop) if resolved_desktop else None,
        "desktop_moved_count": desktop_included_count,
        "moved_count": len(moves),
        "created_dirs_count": len(created_dirs),
        "skipped_hidden_count": skipped_hidden,
        "skipped_partial_count": skipped_partial,
        "skipped_system_desktop_count": skipped_system_desktop,
        "groups": groups_summary,
        "moves": moves,
    }


def record_history(
    history_file: Path,
    target_dir: str,
    mode: str,
    moves: List[dict],
    created_dirs: List[str],
) -> None:
    history_file.parent.mkdir(parents=True, exist_ok=True)
    records = []
    if history_file.is_file():
        try:
            records = json.loads(history_file.read_text(encoding="utf-8"))
        except Exception:
            records = []

    records.append(
        {
            "timestamp": int(time.time()),
            "target_dir": str(Path(target_dir).resolve()),
            "mode": mode,
            "moves": moves,
            "created_dirs": created_dirs,
        }
    )
    # Keep last 50 operations
    records = records[-50:]
    history_file.write_text(
        json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def undo_last_sort(
    target_dir: Optional[Path | str] = None,
    history_path: Optional[Path] = None,
) -> dict:
    """
    Revert the most recent sort operation (for target_dir if given, otherwise global last operation).
    Moves files back to their original paths and removes newly created empty directories.
    """
    history_file = history_path or default_history_path()
    if not history_file.is_file():
        raise RuntimeError("Geri alınacak bir sıralama geçmişi bulunamadı.")

    records = json.loads(history_file.read_text(encoding="utf-8"))
    if not records:
        raise RuntimeError("Geri alınacak bir sıralama geçmişi bulunamadı.")

    target_resolved = str(Path(target_dir).resolve()) if target_dir else None
    match_idx = None

    for idx in range(len(records) - 1, -1, -1):
        if target_resolved is None or records[idx].get("target_dir") == target_resolved:
            match_idx = idx
            break

    if match_idx is None:
        raise RuntimeError(
            f"'{target_resolved}' klasörü için geri alınacak işlem bulunamadı."
        )

    entry = records.pop(match_idx)
    restored_count = 0

    for m in reversed(entry.get("moves", [])):
        src_p = Path(m["src"])
        dst_p = Path(m["dst"])
        if dst_p.is_file():
            src_p.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dst_p), str(src_p))
            restored_count += 1

    removed_dirs = 0
    for d_str in reversed(entry.get("created_dirs", [])):
        d_path = Path(d_str)
        if d_path.is_dir():
            try:
                d_path.rmdir()  # Only removes if empty!
                removed_dirs += 1
            except OSError:
                pass

    history_file.write_text(
        json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return {
        "target_dir": entry.get("target_dir"),
        "restored_count": restored_count,
        "removed_dirs_count": removed_dirs,
    }


def print_report(result: dict) -> None:
    target = result["target_dir"]
    dry_prefix = "[ÖNİZLEME / DRY-RUN] " if result["dry_run"] else ""
    mode_labels = {
        "doctype": "Dosya Uzantısı (--doctype)",
        "category": "Kategori (--category)",
        "date": "Tarih (--date)",
    }
    mode_str = mode_labels.get(result["mode"], result["mode"])

    print(f"\n╭─ {dry_prefix}sortingen v{VERSION}")
    print(f"├─ Klasör : {target}")
    print(f"├─ Mod    : {mode_str}")
    if result.get("include_desktop") and result.get("desktop_dir"):
        print(f"├─ Masaüstü: {result['desktop_dir']} (dahil edildi)")

    if result["moved_count"] == 0:
        print("╰─ Durum  : Düzenlenecek dosya bulunamadı (klasör zaten düzenli).")
        if result["skipped_partial_count"] > 0:
            print(
                f"   ℹ️  İndirmesi devam eden {result['skipped_partial_count']} geçici dosya korundu."
            )
        print()
        return

    print(
        f"├─ Özet   : {result['moved_count']} dosya → {len(result['groups'])} klasöre yerleştirildi"
    )
    print("│")

    for folder_name, info in sorted(
        result["groups"].items(), key=lambda x: (-x[1]["count"], x[0])
    ):
        badge = " [yeni klasör]" if info["newly_created"] else " [mevcut klasör]"
        print(f"│  📁 {folder_name:<12} : {info['count']:>3} dosya{badge}")
        for f_item in info["files"][:5]:
            if f_item["from"] != f_item["to"]:
                print(f"│     ↳ {f_item['from']} → {f_item['to']}")
            else:
                print(f"│     ↳ {f_item['from']}")
        if len(info["files"]) > 5:
            print(f"│     ↳ ... ve {len(info['files']) - 5} dosya daha")

    if result.get("skipped_system_desktop_count", 0) > 0:
        print("│")
        print(
            f"├─ 🖥️  Korunan sistem ikonları: {result['skipped_system_desktop_count']} dosya"
        )

    if result["skipped_partial_count"] > 0:
        print("│")
        print(
            f"├─ ⏳ Korunan aktif indirmeler: {result['skipped_partial_count']} dosya (.crdownload/.part)"
        )

    if not result["dry_run"]:
        print("│")
        print(f"╰─ ↩️  Geri almak için: sortingen \"{target}\" --undo\n")
    else:
        print("│")
        print(
            f"╰─ ✅ Uygulamak için '--dry-run' olmadan çalıştırın: sortingen \"{target}\" --{result['mode']}\n"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sortingen",
        description="Klasördeki dosyaları uzantılarına (--doctype), kategorilerine (--category) veya tarihlerine (--date) göre alt klasörlere ayırır.",
    )
    parser.add_argument(
        "directory",
        nargs="*",
        help="Düzenlenecek klasör yolu veya adı (örn: indirilenler, ~/İndirilenler, .)",
    )
    parser.add_argument(
        "--doctype",
        "-t",
        action="store_true",
        help="Dosyaları kendi uzantı klasörlerine (pdf, docx, jpg, zip vb.) ayırır (varsayılan).",
    )
    parser.add_argument(
        "--category",
        "-c",
        action="store_true",
        help="Dosyaları ana kategorilere (Belgeler, Resimler, Videolar, Müzik, apps, Arşivler vb.) ayırır.",
    )
    parser.add_argument(
        "--date",
        "-d",
        action="store_true",
        help="Dosyaları değiştirilme tarihine (YYYY-AA) göre klasörlere ayırır.",
    )
    parser.add_argument(
        "--include-desktop",
        "-D",
        action="store_true",
        help="Masaüstü (Desktop/Masaüstü) dosyalarını da taramaya dahil eder (sistem ikonları korunur).",
    )
    parser.add_argument(
        "--undo",
        "-u",
        action="store_true",
        help="Son yapılan sıralama işlemini tamamen geri alır.",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
        action="store_true",
        help="Dosyaları taşımadan önce ne yapılacağını önizler.",
    )
    parser.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="Gizli dosyaları (nokta ile başlayanları) da dahil et.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Çıktıyı JSON formatında verir.",
    )
    parser.add_argument(
        "--version",
        "-v",
        action="version",
        version=f"sortingen {VERSION}",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Filter out accidental literal '|' tokens if user typed `sortingen | indirilenler --doctype` with quotes/escapes
    dir_tokens = [tok for tok in (args.directory or []) if tok.strip() != "|"]
    raw_dir = " ".join(dir_tokens).strip()

    # Check piped stdin if no positional directory was provided
    if not raw_dir and not sys.stdin.isatty():
        piped = sys.stdin.read().strip()
        if piped:
            raw_dir = piped.splitlines()[0].strip()

    try:
        if args.undo:
            target = resolve_target_dir(raw_dir) if raw_dir else None
            undo_res = undo_last_sort(target)
            if args.json:
                print(json.dumps(undo_res, indent=2, ensure_ascii=False))
            else:
                print(
                    f"\n↩️  Geri alındı ({undo_res['target_dir']}): "
                    f"{undo_res['restored_count']} dosya eski yerine taşındı, "
                    f"{undo_res['removed_dirs_count']} yeni klasör temizlendi.\n"
                )
            return 0

        target = resolve_target_dir(raw_dir if raw_dir else ".")

        mode = "doctype"
        if args.category:
            mode = "category"
        elif args.date:
            mode = "date"
        elif args.doctype:
            mode = "doctype"

        result = sort_directory(
            target_dir=target,
            mode=mode,
            include_hidden=args.all,
            dry_run=args.dry_run,
            include_desktop=args.include_desktop,
        )

        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print_report(result)
        return 0

    except Exception as exc:
        print(f"Hata: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
