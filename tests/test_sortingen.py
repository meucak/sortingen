#!/usr/bin/env python3
"""
TDD Test Suite for `sortingen` — Smart Directory & File Type Sorter CLI
"""

import os
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
CLI_BIN = PROJECT_ROOT / "bin" / "sortingen"


class TestSortingen(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.history_file = self.root / ".test_history.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_01_doctype_creates_folders_and_moves_files(self):
        """Files are grouped into newly created extension folders under --doctype."""
        import sortingen

        target = self.root / "downloads"
        target.mkdir()
        (target / "rapor.pdf").write_text("pdf1", encoding="utf-8")
        (target / "fatura.PDF").write_text("pdf2", encoding="utf-8")
        (target / "odev.docx").write_text("docx1", encoding="utf-8")
        (target / "ekran.png").write_text("png1", encoding="utf-8")
        (target / "yedek.tar.gz").write_text("targz1", encoding="utf-8")
        (target / "BENIOKU").write_text("noext", encoding="utf-8")

        result = sortingen.sort_directory(
            target, mode="doctype", history_path=self.history_file
        )

        self.assertEqual(result["moved_count"], 6)
        self.assertTrue((target / "pdf" / "rapor.pdf").is_file())
        self.assertTrue((target / "pdf" / "fatura.PDF").is_file())
        self.assertTrue((target / "docx" / "odev.docx").is_file())
        self.assertTrue((target / "png" / "ekran.png").is_file())
        self.assertTrue((target / "tar.gz" / "yedek.tar.gz").is_file())
        self.assertTrue((target / "diger" / "BENIOKU").is_file())

    def test_02_doctype_reuses_existing_case_insensitive_folders(self):
        """If PDF/ or Docx/ already exists, files are placed inside them without creating duplicates."""
        import sortingen

        target = self.root / "indirilenler"
        target.mkdir()
        existing_pdf = target / "PDF"
        existing_docx = target / "Docx"
        existing_pdf.mkdir()
        existing_docx.mkdir()
        (existing_pdf / "eski.pdf").write_text("old", encoding="utf-8")

        (target / "yeni.pdf").write_text("new_pdf", encoding="utf-8")
        (target / "sozlesme.docx").write_text("new_docx", encoding="utf-8")
        (target / " muzik.mp3").write_text("mp3", encoding="utf-8")

        result = sortingen.sort_directory(
            target, mode="doctype", history_path=self.history_file
        )

        self.assertEqual(result["moved_count"], 3)
        self.assertTrue((target / "PDF" / "yeni.pdf").is_file())
        self.assertTrue((target / "PDF" / "eski.pdf").is_file())
        self.assertTrue((target / "Docx" / "sozlesme.docx").is_file())
        self.assertTrue((target / "mp3" / " muzik.mp3").is_file())
        # Ensure no duplicate lowercase 'pdf' directory was created alongside 'PDF'
        dir_names = [p.name for p in target.iterdir() if p.is_dir()]
        self.assertIn("PDF", dir_names)
        self.assertNotIn("pdf", dir_names)
        self.assertIn("Docx", dir_names)
        self.assertNotIn("docx", dir_names)

    def test_03_collision_protection_never_overwrites(self):
        """When destination already has a file with the same name, suffix (1), (2) is added."""
        import sortingen

        target = self.root / "collision_test"
        target.mkdir()
        pdf_dir = target / "pdf"
        pdf_dir.mkdir()
        (pdf_dir / "belge.pdf").write_text("original_content", encoding="utf-8")
        (target / "belge.pdf").write_text("new_content", encoding="utf-8")

        sortingen.sort_directory(
            target, mode="doctype", history_path=self.history_file
        )

        self.assertEqual(
            (pdf_dir / "belge.pdf").read_text(encoding="utf-8"), "original_content"
        )
        self.assertEqual(
            (pdf_dir / "belge (1).pdf").read_text(encoding="utf-8"), "new_content"
        )

    def test_04_skips_hidden_and_partial_downloads(self):
        """Dotfiles and active download temp files (.crdownload, .part, .tmp) are untouched."""
        import sortingen

        target = self.root / "partial_test"
        target.mkdir()
        (target / ". gizli").write_text("hidden", encoding="utf-8")
        (target / "film.mp4.crdownload").write_text("downloading", encoding="utf-8")
        (target / "ubuntu.iso.part").write_text("downloading2", encoding="utf-8")
        (target / "hazir.pdf").write_text("ready", encoding="utf-8")

        result = sortingen.sort_directory(
            target, mode="doctype", history_path=self.history_file
        )

        self.assertEqual(result["moved_count"], 1)
        self.assertEqual(result["skipped_partial_count"], 2)
        self.assertTrue((target / ". gizli").is_file())
        self.assertTrue((target / "film.mp4.crdownload").is_file())
        self.assertTrue((target / "ubuntu.iso.part").is_file())
        self.assertTrue((target / "pdf" / "hazir.pdf").is_file())

    def test_05_smart_turkish_directory_resolution(self):
        """Resolves 'indirilenler' to '~/İndirilenler' with Turkish İ/i/I/ı normalization."""
        import sortingen

        fake_home = self.root / "home_toshi"
        fake_home.mkdir()
        indirilenler = fake_home / "İndirilenler"
        indirilenler.mkdir()

        other_cwd = self.root / "some_other_dir"
        other_cwd.mkdir()

        resolved = sortingen.resolve_target_dir(
            "indirilenler", cwd=other_cwd, home=fake_home
        )
        self.assertEqual(resolved, indirilenler.resolve())

    def test_06_undo_restores_original_state(self):
        """Undo moves files back to original paths and cleans up newly created folders only."""
        import sortingen

        target = self.root / "undo_test"
        target.mkdir()
        pre_existing_pdf = target / "pdf"
        pre_existing_pdf.mkdir()
        (target / "a.pdf").write_text("a", encoding="utf-8")
        (target / "b.docx").write_text("b", encoding="utf-8")

        sortingen.sort_directory(
            target, mode="doctype", history_path=self.history_file
        )
        self.assertTrue((target / "pdf" / "a.pdf").is_file())
        self.assertTrue((target / "docx" / "b.docx").is_file())

        undo_res = sortingen.undo_last_sort(
            target, history_path=self.history_file
        )
        self.assertEqual(undo_res["restored_count"], 2)
        self.assertTrue((target / "a.pdf").is_file())
        self.assertTrue((target / "b.docx").is_file())
        # Pre-existing 'pdf' folder stays, newly created 'docx' folder is removed
        self.assertTrue((target / "pdf").is_dir())
        self.assertFalse((target / "docx").exists())

    def test_07_dry_run_makes_zero_filesystem_changes(self):
        """Dry run calculates moves without touching the disk."""
        import sortingen

        target = self.root / "dry_test"
        target.mkdir()
        (target / "test.pdf").write_text("123", encoding="utf-8")

        res = sortingen.sort_directory(
            target, mode="doctype", dry_run=True, history_path=self.history_file
        )
        self.assertEqual(res["moved_count"], 1)
        self.assertTrue((target / "test.pdf").is_file())
        self.assertFalse((target / "pdf").exists())

    def test_08_cli_argument_and_stdin_pipe_flexibility(self):
        """CLI binary supports `sortingen <dir> --doctype`, `--doctype <dir>`, and piped stdin."""
        t1 = self.root / "cli1"
        t1.mkdir()
        (t1 / "one.pdf").write_text("1", encoding="utf-8")
        (t1 / "two.docx").write_text("2", encoding="utf-8")

        proc1 = subprocess.run(
            [str(CLI_BIN), str(t1), "--doctype"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(proc1.returncode, 0, msg=proc1.stderr)
        self.assertTrue((t1 / "pdf" / "one.pdf").is_file())
        self.assertTrue((t1 / "docx" / "two.docx").is_file())

        # Also test piped stdin: `echo <dir> | sortingen --doctype`
        t2 = self.root / "cli2"
        t2.mkdir()
        (t2 / "three.jpg").write_text("3", encoding="utf-8")
        proc2 = subprocess.run(
            [str(CLI_BIN), "--doctype"],
            input=f"{t2}\n",
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(proc2.returncode, 0, msg=proc2.stderr)
        self.assertTrue((t2 / "jpg" / "three.jpg").is_file())

    def test_09_extensionless_file_named_same_as_doctype_folder(self):
        """If an extensionless file named 'pdf' exists alongside 'doc.pdf', both move cleanly without FileExistsError."""
        import sortingen

        target = self.root / "name_clash"
        target.mkdir()
        (target / "pdf").write_text("extensionless file named pdf", encoding="utf-8")
        (target / "doc.pdf").write_text("actual pdf document", encoding="utf-8")

        res = sortingen.sort_directory(
            target, mode="doctype", history_path=self.history_file
        )
        self.assertEqual(res["moved_count"], 2)
        self.assertTrue((target / "diger" / "pdf").is_file())
        self.assertTrue((target / "pdf" / "doc.pdf").is_file())

    def test_10_category_reuses_existing_xdg_and_creates_apps(self):
        """Category mode reuses existing XDG/alias folders and maps apps, media, logs, archives cleanly."""
        import sortingen

        target = self.root / "home_sim"
        target.mkdir()
        (target / "Resimler").mkdir()
        (target / "Documents").mkdir()
        (target / "Music").mkdir()
        (target / "Videos").mkdir()

        (target / "foto.png").write_text("img", encoding="utf-8")
        (target / "klip.mp4").write_text("vid", encoding="utf-8")
        (target / "sarki.mp3").write_text("aud", encoding="utf-8")
        (target / "rapor.pdf").write_text("pdf", encoding="utf-8")
        (target / "kayit.log").write_text("log", encoding="utf-8")
        (target / "yedek.iso").write_text("iso", encoding="utf-8")
        (target / "app.apk").write_text("apk", encoding="utf-8")
        (target / "script.sh").write_text("sh", encoding="utf-8")
        (target / "tool.py").write_text("py", encoding="utf-8")
        (target / "kisayol.desktop").write_text("desk", encoding="utf-8")

        res = sortingen.sort_directory(
            target, mode="category", history_path=self.history_file
        )

        self.assertEqual(res["moved_count"], 10)
        self.assertTrue((target / "Resimler" / "foto.png").is_file())
        self.assertTrue((target / "Videos" / "klip.mp4").is_file())
        self.assertTrue((target / "Music" / "sarki.mp3").is_file())
        self.assertTrue((target / "Documents" / "rapor.pdf").is_file())
        self.assertTrue((target / "Documents" / "kayit.log").is_file())
        self.assertTrue((target / "Arşivler" / "yedek.iso").is_file())
        self.assertTrue((target / "apps" / "app.apk").is_file())
        self.assertTrue((target / "apps" / "script.sh").is_file())
        self.assertTrue((target / "apps" / "tool.py").is_file())
        self.assertTrue((target / "apps" / "kisayol.desktop").is_file())
        self.assertFalse((target / "Videolar").exists())
        self.assertFalse((target / "Belgeler").exists())
        self.assertFalse((target / "Müzik").exists())

    def test_11_doctype_avoids_desktop_folder_collision(self):
        """In doctype mode, .desktop files never move into Desktop/Masaüstü when it exists; normal subdirs still use desktop/."""
        import sortingen

        home_like = self.root / "home_desktop_clash"
        home_like.mkdir()
        (home_like / "Desktop").mkdir()
        (home_like / "app.desktop").write_text("[Desktop Entry]", encoding="utf-8")

        res1 = sortingen.sort_directory(
            home_like, mode="doctype", history_path=self.history_file
        )
        self.assertEqual(res1["moved_count"], 1)
        self.assertFalse((home_like / "Desktop" / "app.desktop").exists())
        self.assertTrue((home_like / "desktop_shortcuts" / "app.desktop").is_file())

        # When 'apps' already exists alongside Desktop, doctype uses apps
        home_with_apps = self.root / "home_with_apps"
        home_with_apps.mkdir()
        (home_with_apps / "Desktop").mkdir()
        (home_with_apps / "apps").mkdir()
        (home_with_apps / "borfek.desktop").write_text("[Desktop Entry]", encoding="utf-8")
        res2 = sortingen.sort_directory(
            home_with_apps, mode="doctype", history_path=self.history_file
        )
        self.assertEqual(res2["moved_count"], 1)
        self.assertTrue((home_with_apps / "apps" / "borfek.desktop").is_file())

        # Inside a normal folder (e.g. apps/), doctype still creates desktop/
        apps_dir = self.root / "apps_dir"
        apps_dir.mkdir()
        (apps_dir / "kush.desktop").write_text("[Desktop Entry]", encoding="utf-8")
        res3 = sortingen.sort_directory(
            apps_dir, mode="doctype", history_path=self.history_file
        )
        self.assertEqual(res3["moved_count"], 1)
        self.assertTrue((apps_dir / "desktop" / "kush.desktop").is_file())

    def test_12_include_desktop_preserves_system_icons_and_supports_undo(self):
        """--include-desktop moves non-system Desktop files, keeps system icons, and supports undo."""
        import sortingen

        fake_home = self.root / "toshi_home"
        fake_home.mkdir()
        desktop = fake_home / "Desktop"
        desktop.mkdir()
        belgeler = fake_home / "Belgeler"
        belgeler.mkdir()

        # Main home files
        (fake_home / "aura-lan.apk").write_text("apk", encoding="utf-8")
        (fake_home / "log.txt").write_text("log", encoding="utf-8")
        # Desktop files (system icons + regular files)
        (desktop / "computer.desktop").write_text("sys1", encoding="utf-8")
        (desktop / "trash-can.desktop").write_text("sys2", encoding="utf-8")
        (desktop / "user-home.desktop").write_text("sys3", encoding="utf-8")
        (desktop / "network.desktop").write_text("sys4", encoding="utf-8")
        (desktop / "borfek.desktop").write_text("app1", encoding="utf-8")
        (desktop / "kilavuz.txt").write_text("doc1", encoding="utf-8")

        res = sortingen.sort_directory(
            fake_home,
            mode="category",
            include_desktop=True,
            desktop_dir=desktop,
            history_path=self.history_file,
        )

        self.assertEqual(res["moved_count"], 4)
        self.assertEqual(res["skipped_system_desktop_count"], 4)
        self.assertTrue((fake_home / "apps" / "aura-lan.apk").is_file())
        self.assertTrue((fake_home / "apps" / "borfek.desktop").is_file())
        self.assertTrue((belgeler / "log.txt").is_file())
        self.assertTrue((belgeler / "kilavuz.txt").is_file())
        # System icons remain untouched on Desktop
        for icon_name in (
            "computer.desktop",
            "trash-can.desktop",
            "user-home.desktop",
            "network.desktop",
        ):
            self.assertTrue((desktop / icon_name).is_file())

        # Undo restores both home and desktop files and removes newly created 'apps'
        undo_res = sortingen.undo_last_sort(fake_home, history_path=self.history_file)
        self.assertEqual(undo_res["restored_count"], 4)
        self.assertTrue((fake_home / "aura-lan.apk").is_file())
        self.assertTrue((fake_home / "log.txt").is_file())
        self.assertTrue((desktop / "borfek.desktop").is_file())
        self.assertTrue((desktop / "kilavuz.txt").is_file())
        self.assertFalse((fake_home / "apps").exists())
        self.assertTrue(belgeler.is_dir())

    def test_13_cli_include_desktop_flag(self):
        """CLI supports --category --include-desktop (-c -D) and records undo history."""
        fake_home = self.root / "cli_home"
        fake_home.mkdir()
        desktop = fake_home / "Desktop"
        desktop.mkdir()
        (fake_home / "Belgeler").mkdir()
        (desktop / "computer.desktop").write_text("sys", encoding="utf-8")
        (desktop / "kush.desktop").write_text("app", encoding="utf-8")
        (desktop / "readme.txt").write_text("doc", encoding="utf-8")
        (fake_home / "script.py").write_text("py", encoding="utf-8")

        env = os.environ.copy()
        env["HOME"] = str(fake_home)
        env["XDG_CACHE_HOME"] = str(fake_home / ".cache")
        env.pop("XDG_DESKTOP_DIR", None)

        proc = subprocess.run(
            [str(CLI_BIN), str(fake_home), "--category", "--include-desktop"],
            capture_output=True,
            text=True,
            env=env,
            timeout=5,
        )
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        self.assertTrue((fake_home / "apps" / "kush.desktop").is_file())
        self.assertTrue((fake_home / "apps" / "script.py").is_file())
        self.assertTrue((fake_home / "Belgeler" / "readme.txt").is_file())
        self.assertTrue((desktop / "computer.desktop").is_file())
        self.assertFalse((desktop / "kush.desktop").exists())
        self.assertFalse((desktop / "readme.txt").exists())

        undo_proc = subprocess.run(
            [str(CLI_BIN), str(fake_home), "--undo"],
            capture_output=True,
            text=True,
            env=env,
            timeout=5,
        )
        self.assertEqual(undo_proc.returncode, 0, msg=undo_proc.stderr)
        self.assertTrue((desktop / "kush.desktop").is_file())
        self.assertTrue((desktop / "readme.txt").is_file())
        self.assertTrue((fake_home / "script.py").is_file())


if __name__ == "__main__":
    unittest.main()
