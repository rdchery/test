"""Destinations a downloaded fax can be written to: a locally mounted
network share, or a share reached directly over SMB.
"""
import os
from pathlib import Path


class LocalShareWriter:
    """Writes to a filesystem path -- a Windows mapped drive or a
    Linux CIFS/NFS mount point that is already mounted on this host."""

    def __init__(self, share_dir):
        self.share_dir = Path(share_dir)

    def write(self, filename, content):
        self.share_dir.mkdir(parents=True, exist_ok=True)
        dest = self.share_dir / filename
        tmp = dest.with_name(dest.name + ".part")
        tmp.write_bytes(content)
        tmp.rename(dest)
        return dest


class SmbShareWriter:
    """Writes directly to an SMB share over the network, without
    requiring the OS to have it mounted. Requires the `smbprotocol`
    package (imported lazily so it's only needed when actually used)."""

    def __init__(self, host, share, username, password, remote_dir="", port=445):
        from smbclient import mkdir, open_file, register_session

        self._mkdir = mkdir
        self._open_file = open_file
        self.host = host
        self.share = share
        self.remote_dir = remote_dir.strip("/\\")
        register_session(host, username=username, password=password, port=port)

    def _unc(self, *parts):
        return "\\".join([f"\\\\{self.host}\\{self.share}", *parts])

    def write(self, filename, content):
        if self.remote_dir:
            try:
                self._mkdir(self._unc(self.remote_dir))
            except OSError:
                pass  # already exists
        dest = self._unc(self.remote_dir, filename) if self.remote_dir else self._unc(filename)
        with self._open_file(dest, mode="wb") as f:
            f.write(content)
        return dest


def build_share_writer_from_env(env=None):
    env = env if env is not None else os.environ
    if env.get("SMB_HOST"):
        return SmbShareWriter(
            host=env["SMB_HOST"],
            share=env["SMB_SHARE"],
            username=env.get("SMB_USERNAME"),
            password=env.get("SMB_PASSWORD"),
            remote_dir=env.get("SMB_REMOTE_DIR", ""),
            port=int(env.get("SMB_PORT", 445)),
        )
    share_dir = env.get("SHARE_DIR")
    if not share_dir:
        raise ValueError(
            "Set SHARE_DIR (a mounted path) or SMB_HOST/SMB_SHARE/SMB_USERNAME/SMB_PASSWORD "
            "(direct SMB) in the environment"
        )
    return LocalShareWriter(share_dir)
