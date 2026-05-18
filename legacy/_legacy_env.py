"""Legacy ``.env`` parser used only by ``legacy/javdb_magnet_gui.py``.

Moved out of ``realdebrid.py`` (F-06) so the production module no longer
exports a generic dotenv parser that future callers could misuse. The
live sidecar receives credentials via :mod:`sidecar.sidecar` handshake +
OS keyring; the Rust ``settings`` module owns settings persistence.
``legacy.javdb_magnet_gui`` is the only legitimate caller and is not
bundled into ``sidecar.exe`` / ``javdbmagnet.exe``.
"""

from pathlib import Path


def load_env(path: Path) -> dict[str, str]:
    """簡易 .env 檔案解析器（legacy GUI 專用）。

    .. deprecated::
        Legacy only — kept solely for ``legacy/javdb_magnet_gui.py`` and
        its tests. New code paths MUST NOT call this: re-introducing it
        on the production path would re-open the F-06 finding (any
        ``key=value`` line in an attacker-controlled file becomes config).
    """
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env
