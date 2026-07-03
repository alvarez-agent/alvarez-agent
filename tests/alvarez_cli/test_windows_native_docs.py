from pathlib import Path


def test_windows_native_install_path_docs_match_installer() -> None:
    doc = Path("website/docs/user-guide/windows-native.md").read_text()
    install = Path("scripts/install.ps1").read_text()

    assert "%LOCALAPPDATA%\\alvarez\\alvarez-agent\\venv\\Scripts" in doc
    assert "Get-Command alvarez        # should print C:\\Users\\<you>\\AppData\\Local\\alvarez\\alvarez-agent\\venv\\Scripts\\alvarez.exe" in doc
    assert '$alvarezBin = "$InstallDir\\venv\\Scripts"' in install
