"""Regression tests for the Windows launcher/path-quoting bug: a quoted
`%~dp0`-derived argument with nothing appended after it (so it ends in a
trailing backslash immediately before the closing quote) has its closing
quote consumed as a literal character by Windows' argv parsing (an odd
number of backslashes before a `"` escapes it), leaking a literal `"`
into the received argument and causing WinError 123.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from strengthening.human_annotation.gui.main import clean_path_arg

PACKAGE_DIR = Path(__file__).resolve().parents[1] / "restricted_local" / "human_annotation" / "v1"

# The tests below (5-9) read the real, deployed START_ANNOTATOR_<N>.bat launcher
# files, which ship only inside the private annotator-deployment package
# (bundled there for one-click distribution alongside the real annotation
# workbooks; gitignored, not distributed in the public release -- see
# strengthening/restricted_local/). They provide genuine public methodological
# value (they regression-test a real Windows launcher bug fix, and one of them
# is itself a privacy check that the launcher never leaks scientific terms),
# so they are retained and run normally whenever the package is actually
# present; they are explicitly skipped, not weakened, when it is not.
requires_restricted_launcher_package = pytest.mark.skipif(
    not (PACKAGE_DIR / "START_ANNOTATOR_1.bat").exists(),
    reason="requires restricted local research fixture (deployed annotator launcher package); not distributed in public release",
)


# -- 1. Windows path with spaces -----------------------------------------

def test_clean_path_arg_handles_spaces_in_path():
    p = clean_path_arg(r"C:\Example Folder\Article 7\annotation\v1")
    assert "Article 7" in str(p)
    assert '"' not in str(p)


# -- 2. accidental surrounding quotes -------------------------------------

def test_clean_path_arg_strips_accidental_surrounding_quotes():
    raw = '"C:\\Example Folder\\Article 7\\annotation\\v1"'
    p = clean_path_arg(raw)
    assert '"' not in str(p)
    assert str(p).endswith("v1")


def test_clean_path_arg_strips_the_exact_observed_bug_pattern():
    # Reproduces the literal string reported in the real error message.
    raw = (
        '"C:\\Users\\ExampleUser\\Downloads\\PhD\\Article '
        '7\\concept_harmonisation-strengthening-2026\\strengthening\\'
        'restricted_local\\human_annotation\\v1"'
    )
    p = clean_path_arg(raw)
    assert '"' not in str(p)
    assert str(p).endswith("v1")


# -- 3. %~dp0 trailing-backslash bug, reproduced and fixed at the OS level --

def _run_cmd_snippet(snippet: str, tmp_path: Path) -> str:
    """Writes the snippet to an actual temporary .bat file and executes
    THAT FILE (rather than passing an already-quoted command string as one
    element of a subprocess.run() argv list -- Python's own list2cmdline
    re-escaping would then double-quote it, an unrelated nested-quoting
    artefact of the test harness, not of the real launcher). Executing a
    real .bat file is also more faithful to how START_ANNOTATOR_<N>.bat
    actually runs. Returns what the child process actually received."""
    bat_path = tmp_path / "probe.bat"
    bat_path.write_text("@echo off\r\n" + snippet + "\r\n", encoding="utf-8")
    result = subprocess.run(
        ["cmd.exe", "/c", str(bat_path)],
        capture_output=True, text=True, timeout=30,
    )
    return (result.stdout or "") + (result.stderr or "")


@pytest.mark.skipif(subprocess.run(["where", "cmd.exe"], capture_output=True).returncode != 0, reason="cmd.exe not available")
def test_trailing_backslash_before_quote_is_the_real_bug(tmp_path):
    """Demonstrates the BUG at the real Windows command-line-parsing level:
    a quoted argument ending in a backslash-then-quote leaks a literal `"`
    into the receiving process's argv."""
    printer = tmp_path / "print_argv.py"
    printer.write_text("import sys; print(repr(sys.argv[1]))\n", encoding="utf-8")

    # Simulates: set "SCRIPT_DIR=C:\some\dir\"  (trailing backslash from %~dp0)
    #            program "%SCRIPT_DIR%"          <-- the buggy pattern
    buggy_dir = str(tmp_path) + "\\"  # trailing backslash, like %~dp0 always has
    snippet = f'python "{printer}" "{buggy_dir}"'
    output = _run_cmd_snippet(snippet, tmp_path)
    assert '"' in output, (
        f"expected the classic trailing-backslash-before-quote bug to leak a literal quote "
        f"into argv, but got: {output!r}"
    )


@pytest.mark.skipif(subprocess.run(["where", "cmd.exe"], capture_output=True).returncode != 0, reason="cmd.exe not available")
def test_stripping_trailing_backslash_before_quoting_fixes_it(tmp_path):
    """Proves the FIX: stripping the trailing backslash from SCRIPT_DIR
    before quoting it (exactly what START_ANNOTATOR_<N>.bat now does)
    eliminates the literal-quote leak."""
    printer = tmp_path / "print_argv.py"
    printer.write_text("import sys; print(repr(sys.argv[1]))\n", encoding="utf-8")

    fixed_dir = str(tmp_path)  # no trailing backslash -- the fix
    snippet = f'python "{printer}" "{fixed_dir}"'
    output = _run_cmd_snippet(snippet, tmp_path)
    assert output.count("'") == 2, f"expected a clean single-quoted repr with no stray embedded quotes, got: {output!r}"
    received_arg = eval(output.strip())  # the argv[1] repr the child process actually printed
    assert received_arg == str(tmp_path)


# -- 4. no embedded quote survives into Path -----------------------------

def test_no_embedded_quote_survives_into_path_object():
    p = clean_path_arg('"C:\\a\\b\\c"')
    assert '"' not in str(p)
    for part in p.parts:
        assert '"' not in part


# -- 5/6. Annotator 1/2 launcher target ----------------------------------

@requires_restricted_launcher_package
def test_annotator_1_launcher_binds_to_annotator_1_source_only():
    text = (PACKAGE_DIR / "START_ANNOTATOR_1.bat").read_text(encoding="utf-8")
    assert "--annotator-id 1" in text
    assert "01_ANNOTATOR_1_PRIMARY.xlsx" in text
    assert "02_ANNOTATOR_2_PRIMARY.xlsx" not in text


@requires_restricted_launcher_package
def test_annotator_2_launcher_binds_to_annotator_2_source_only():
    text = (PACKAGE_DIR / "START_ANNOTATOR_2.bat").read_text(encoding="utf-8")
    assert "--annotator-id 2" in text
    assert "02_ANNOTATOR_2_PRIMARY.xlsx" in text
    assert "01_ANNOTATOR_1_PRIMARY.xlsx" not in text


# -- 7/8. BAT command construction with pythonw.exe / python.exe fallback --

@requires_restricted_launcher_package
@pytest.mark.parametrize("bat_name", ["START_ANNOTATOR_1.bat", "START_ANNOTATOR_2.bat"])
def test_bat_uses_pythonw_directly_without_start(bat_name):
    text = (PACKAGE_DIR / bat_name).read_text(encoding="utf-8")
    # the pythonw.exe branch must not be wrapped in `start` (unnecessary --
    # pythonw already has no console -- and `start` adds first-quoted-token
    # window-title ambiguity risk for no benefit).
    assert "goto :launch_pythonw" in text
    # split on the LABEL LINE itself (newline-bounded), not the earlier
    # "goto :launch_pythonw" reference which also contains this substring.
    launch_block = text.split("\n:launch_pythonw\n")[1].split(":python_missing")[0]
    assert "pythonw.exe -m strengthening" in launch_block
    assert "start " not in launch_block


@requires_restricted_launcher_package
@pytest.mark.parametrize("bat_name", ["START_ANNOTATOR_1.bat", "START_ANNOTATOR_2.bat"])
def test_bat_python_fallback_uses_correct_start_syntax(bat_name):
    text = (PACKAGE_DIR / bat_name).read_text(encoding="utf-8")
    # start "" /min "python.exe" ... -- the empty "" title MUST come first,
    # per the well-known `start` first-quoted-token-is-the-title gotcha.
    assert 'start "" /min python.exe -m strengthening' in text


@requires_restricted_launcher_package
@pytest.mark.parametrize("bat_name", ["START_ANNOTATOR_1.bat", "START_ANNOTATOR_2.bat"])
def test_bat_never_quotes_script_dir_alone_with_trailing_backslash(bat_name):
    """The actual regression check for the reported bug: SCRIPT_DIR must
    have its trailing backslash stripped before any use, and --package-dir
    must never be passed as a bare quoted %~dp0-style variable."""
    text = (PACKAGE_DIR / bat_name).read_text(encoding="utf-8")
    assert 'if "%SCRIPT_DIR:~-1%"=="\\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"' in text
    # every quoted use of SCRIPT_DIR must either add a path component after it
    # (...\something) or, for the bare --package-dir case, SCRIPT_DIR itself
    # must no longer carry a trailing backslash (guaranteed by the strip
    # above, so a bare "%SCRIPT_DIR%" is now safe).
    assert '"%SCRIPT_DIR%\\..\\..\\..\\.."' in text


# -- 9. no scientific/system metadata exposure introduced ------------------

@requires_restricted_launcher_package
@pytest.mark.parametrize("bat_name", ["START_ANNOTATOR_1.bat", "START_ANNOTATOR_2.bat"])
def test_bat_still_exposes_no_forbidden_terms(bat_name):
    text = (PACKAGE_DIR / bat_name).read_text(encoding="utf-8").lower()
    for term in ("stratum", "jaro", "embedding", "anthropic", "openai", "api_key", "gold"):
        assert term not in text
