from __future__ import annotations

import configparser
import os
from pathlib import Path

try:
    import winreg
except ModuleNotFoundError:
    winreg = None


_REG_PATH = r"Software\TradeDangerous"
_REG_NAME = "InstallChannel"
_REG_VALUE = "packaged"
_SQLITE_FILENAME = "TradeDangerous.db"
_BOOTSTRAP_RESULT: dict[str, object] | None = None


def _detect_packaged_mode() -> bool:
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _REG_PATH) as key:
            value, reg_type = winreg.QueryValueEx(key, _REG_NAME)
    except OSError:
        return False
    return reg_type == winreg.REG_SZ and str(value).strip().lower() == _REG_VALUE


def _get_packaged_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise RuntimeError("Packaged mode requires LOCALAPPDATA to be set.")
    return Path(local_app_data).expanduser() / "TradeDangerous"


def _write_packaged_config(cfg_path: Path, data_dir: Path, tmp_dir: Path) -> None:
    cp = configparser.ConfigParser()
    cp["database"] = {"backend": "sqlite"}
    cp["sqlite"] = {"sqlite_filename": _SQLITE_FILENAME}
    cp["paths"] = {
        "data_dir": str(data_dir),
        "tmp_dir": str(tmp_dir),
    }
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    with cfg_path.open("w", encoding="utf-8") as fh:
        cp.write(fh)


def bootstrap_runtime() -> dict[str, object]:
    global _BOOTSTRAP_RESULT

    if _BOOTSTRAP_RESULT is not None:
        return dict(_BOOTSTRAP_RESULT)

    result: dict[str, object] = {
        "packaged_mode": False,
        "app_root": None,
        "db_config": None,
        "data_dir": None,
        "tmp_dir": None,
        "logs_dir": None,
    }

    if not _detect_packaged_mode():
        _BOOTSTRAP_RESULT = result
        return dict(result)

    app_root = _get_packaged_root()
    db_config = app_root / "db_config.ini"
    data_dir = app_root / "data"
    tmp_dir = app_root / "tmp"
    logs_dir = app_root / "logs"

    data_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    os.environ["TD_DB_CONFIG"] = str(db_config)
    os.environ["TD_DATA"] = str(data_dir)
    os.environ["TD_TMP"] = str(tmp_dir)

    if not db_config.exists():
        _write_packaged_config(db_config, data_dir, tmp_dir)

    result.update(
        {
            "packaged_mode": True,
            "app_root": app_root,
            "db_config": db_config,
            "data_dir": data_dir,
            "tmp_dir": tmp_dir,
            "logs_dir": logs_dir,
        }
    )
    _BOOTSTRAP_RESULT = result
    return dict(result)
