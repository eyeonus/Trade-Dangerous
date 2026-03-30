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

### Notes

- This procedure is for the **GUI** freeze path, not the CLI.
- The freeze target is defined by `TradeDangerous.spec`.
- Build from a clean checkout, not from a cluttered day-to-day development tree.
- The spec file is the authoritative freeze recipe; do not reconstruct the full PyInstaller command by hand unless you are deliberately updating the freeze configuration.


## Windows installer packaging procedure

1. Install Inno Setup if it is not already present.

   The simplest documented method is download from https://jrsoftware.org/isinfo.php and go with default install.

   This procedure assumes Inno Setup is then installed in its normal location and that the command-line compiler `ISCC.exe` is available there.

2. Ensure you already have a current frozen GUI bundle built from the checked-in PyInstaller spec.

   The installer packages the existing frozen output. It does **not** build the application itself.

   Expected frozen bundle location:

   ```text
   dist\TradeDangerous\
   ```

   Executable inside that bundle:

   ```text
   dist\TradeDangerous\TradeDangerous.exe
   ```

3. Update the Inno Setup script for the current release.

   Open `TradeDangerous.iss` and update the release-specific version fields:

   - `AppVersion`
   - `OutputBaseFilename`

   Example pattern:

   ```text
   OutputBaseFilename=TradeDangerous-Setup-12.18.7
   ```

   Keep the following values stable unless there is a deliberate packaging-policy change:

   - `AppId=TradeDangerous`
   - default install location under `%ProgramFiles%`
   - Start Menu group name
   - packaged registry marker under `HKLM\Software\TradeDangerous`

4. Confirm that the installer script is packaging the correct frozen payload.

   The current installer script is expected to package the full frozen bundle from:

   ```text
   dist\TradeDangerous\*
   ```

   That includes:
   - `TradeDangerous.exe`
   - the `_internal` directory
   - any other files produced by the PyInstaller onedir build

5. Compile the installer from the repo root using the Inno Setup command-line compiler.

   Example:

   ```powershell
   & "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" ".\TradeDangerous.iss"
   ```

6. Locate the generated installer output.

   By default, the compiled installer is written to the output directory produced by Inno Setup for the script, using the filename defined by `OutputBaseFilename`.

   Example result:

   ```text
   Output\TradeDangerous-Setup-12.18.7.exe
   ```

7. Perform a clean install test before release.

   Recommended test approach:

   - uninstall any previous packaged copy
   - remove any manually created test registry marker if applicable
   - remove `%LOCALAPPDATA%\TradeDangerous` if you want to simulate a first packaged run
   - run the new installer
   - complete the install wizard
   - launch the installed application

8. Confirm the installed package behaves correctly.

   Minimum sanity checks:

   - application installs into `%ProgramFiles%\TradeDangerous` by default
   - Start Menu shortcut is created
   - Desktop shortcut is created only if selected
   - installer writes the packaged-mode registry marker:
     - `HKLM\Software\TradeDangerous`
     - `InstallChannel=packaged`
   - first launch creates and uses `%LOCALAPPDATA%\TradeDangerous`
   - the installed application starts and behaves as expected for a reasonable smoke test

9. Test uninstall behaviour.

   Confirm that uninstall:
   - removes installed files
   - removes shortcuts
   - removes the packaged registry key
   - asks whether to remove `%LOCALAPPDATA%\TradeDangerous`
   - defaults that data-removal prompt to **No**

10. Treat the compiled installer as the release-ready Windows installer artifact only after the install and uninstall checks pass.

### Notes

- This procedure packages the **GUI** application only.
- This is a **Windows-native** process.
- The checked-in file `TradeDangerous.iss` is the authoritative installer recipe.
- Do not rebuild the installer by hand from ad-hoc GUI clicks; use the checked-in script and the command-line compiler.
- The installer is unsigned unless code signing is added later, so Windows UAC will show **Unknown publisher**. That is expected for an unsigned build.