# Windows executable release procedure.

To create the installable windows release there are three steps.

1. Have a working python release.
2. Freeze the python release into a windows executable.
3. Package the executable into the installer.

## Working Python Release

This may seem blindingly obvious, but to go through this procedure for every tiny bugfix might be excessive. We want to checkpoint good working builds of TD, which we can release, then continue development via the normal schedule of python releases. Once we're happy we've done enough to justify a windows release and again it's a solid stable checkpoint, we can go through this again. It's not terribly hard, but it's a lot more work than `git push`.

## Windows GUI freeze procedure

1. Create a clean release workspace outside your normal development tree.

   Example layout:

   ```text
   D:\TDRelease\
       .venv-freeze\
       Trade-Dangerous\
   ```

2. Create and activate a dedicated freeze virtual environment.

   ```powershell
   py -3.14 -m venv D:\TDRelease\.venv-freeze
   D:\TDRelease\.venv-freeze\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install pyinstaller
   ```

3. Clone the repository into the clean workspace and change into the repo root.

   ```powershell
   cd D:\TDRelease
   git clone <REPO-URL> Trade-Dangerous
   cd D:\TDRelease\Trade-Dangerous
   ```

4. Install Trade Dangerous and its dependencies into the freeze virtual environment.

   ```powershell
   pip install .
   ```

5. Build the Windows GUI bundle from the checked-in PyInstaller spec file.

   ```powershell
   pyinstaller --noconfirm --clean TradeDangerous.spec
   ```

6. Locate the frozen output in the dist directory.

   ```text
   dist\TradeDangerous\
   ```

   Executable:

   ```text
   dist\TradeDangerous\TradeDangerous.exe
   ```

7. Run the frozen executable and perform a basic smoke test.

   ```powershell
   .\dist\TradeDangerous\TradeDangerous.exe
   ```

8. Confirm that:
   - the application starts
   - the window icon is correct
   - the GUI loads correctly
   - the basic workflows you care about behave as expected

9. If the smoke test is satisfactory, treat the contents of `dist\TradeDangerous\` as the release-ready frozen GUI bundle for the next packaging stage.

## Notes

- This procedure is for the **GUI** freeze path, not the CLI.
- The freeze target is defined by `TradeDangerous.spec`.
- Build from a clean checkout, not from a cluttered day-to-day development tree.
- The spec file is the authoritative freeze recipe; do not reconstruct the full PyInstaller command by hand unless you are deliberately updating the freeze configuration.
