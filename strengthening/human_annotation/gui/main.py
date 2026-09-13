"""M7 annotation GUI entrypoint. Invoked by START_ANNOTATOR_<N>.bat, never
by the annotator directly. Validates inputs before opening any window;
on failure shows a graphical error dialog (no console interaction
required) and exits non-zero.

Usage:
    python -m strengthening.human_annotation.gui.main --annotator-id 1 \
        --source "<...>/01_ANNOTATOR_1_PRIMARY.xlsx" \
        --context-ce "<...>/05_CONTEXT_LOOKUP_CE.xlsx" \
        --context-diabetes "<...>/06_CONTEXT_LOOKUP_DIABETES.xlsx" \
        --package-dir "<...>/restricted_local/human_annotation/v1"
"""
from __future__ import annotations

import argparse
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from .app import App
from .context_lookup import CombinedContextLookup
from .session import AnnotationSession
from .validation import ValidationError, validate_context_lookup, validate_source_workbook


def _fatal_error_dialog(message: str) -> None:
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("M7 Annotation GUI - Cannot Start", message)
    root.destroy()


def clean_path_arg(raw: str) -> Path:
    """argparse `type=` for path arguments: defensively strips accidental
    surrounding double-quote characters before constructing a Path.

    This is a belt-and-suspenders safety net, not the primary fix for the
    Windows launcher bug (see START_ANNOTATOR_<N>.bat, which no longer
    quotes a `%~dp0`-derived variable with nothing appended after it --
    that trailing-backslash-before-closing-quote pattern is what let a
    literal `"` leak into argv in the first place). `"` can never
    legitimately appear inside a real Windows path (it is one of the
    characters Windows reserves and refuses in file/directory names), so
    stripping it from the argument's edges can never mask a genuinely
    malformed *internal* path -- only ever undoes exactly this class of
    quoting artefact.
    """
    cleaned = raw.strip('"')
    return Path(cleaned).resolve()


def _expected_manifest_hash(package_dir: Path, annotator_id: str) -> str | None:
    # strengthening/provenance/final_annotation_package_manifest.json records hashes of the
    # *pristine benchmark* source files (CE 400 / biomedical 500), not of each annotator's
    # already-shuffled workbook view -- there is no matching per-annotator hash to check
    # against, so this intentionally returns None (validate_source_workbook then skips the
    # hash-comparison warning and relies on its structural checks instead).
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="M7 local annotation GUI")
    parser.add_argument("--annotator-id", required=True, choices=["1", "2"])
    parser.add_argument("--source", required=True, type=clean_path_arg)
    parser.add_argument("--context-ce", required=True, type=clean_path_arg)
    parser.add_argument("--context-diabetes", required=True, type=clean_path_arg)
    parser.add_argument("--package-dir", required=True, type=clean_path_arg)
    args = parser.parse_args(argv)

    annotator_label = f"Annotator {args.annotator_id}"

    try:
        expected_hash = _expected_manifest_hash(args.package_dir, args.annotator_id)
        validate_source_workbook(args.source, expected_manifest_hash=expected_hash)
        validate_context_lookup(args.context_ce)
        validate_context_lookup(args.context_diabetes)
    except ValidationError as e:
        _fatal_error_dialog(str(e))
        return 1
    except Exception as e:  # noqa: BLE001 -- surface any unexpected failure to the annotator, not a stack trace
        _fatal_error_dialog(f"Unexpected error while validating inputs:\n{e}")
        return 1

    package_dir: Path = args.package_dir
    working_path = package_dir / f"ANNOTATOR_{args.annotator_id}_PRIMARY_WORKING.xlsx"
    completed_path = package_dir / f"ANNOTATOR_{args.annotator_id}_PRIMARY_COMPLETED.xlsx"
    audit_log_path = package_dir / "logs" / f"ANNOTATOR_{args.annotator_id}_PRIMARY_audit_log.csv"
    backup_dir = package_dir / "backups"

    try:
        session = AnnotationSession(
            annotator_id=annotator_label,
            source_path=args.source,
            working_path=working_path,
            completed_path=completed_path,
            audit_log_path=audit_log_path,
            backup_dir=backup_dir,
        )
        context = CombinedContextLookup(args.context_ce, args.context_diabetes)
    except Exception as e:  # noqa: BLE001
        _fatal_error_dialog(f"Could not start the annotation session:\n{e}")
        return 1

    app = App(session, context, annotator_label)
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
