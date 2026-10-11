from cbpi.utils.encoder import ComplexEncoder

__all__ = ["load_config", "json_dumps", "write_json_atomic", "set_aside_corrupt_file"]

import json
import logging
import os
import tempfile
from datetime import datetime

import yaml


def load_config(fname):

    try:
        with open(fname, "rt") as f:
            data = yaml.load(f, Loader=yaml.FullLoader)
        return data
    except Exception as e:

        pass


def json_dumps(obj):
    return json.dumps(obj, cls=ComplexEncoder)


def _file_mode(path):
    try:
        return os.stat(path).st_mode & 0o777
    except OSError:
        umask = os.umask(0)
        os.umask(umask)
        return 0o666 & ~umask


def write_json_atomic(path, data, **kwargs):
    """
    Write data as JSON to path without ever leaving a truncated file behind.

    The data is dumped to a temp file in the same directory, flushed and
    fsynced, then moved onto the target with os.replace (atomic on POSIX).
    A power cut during the write leaves either the old or the new content.

    :param path: target file
    :param data: JSON serializable data
    :param kwargs: extra json.dump arguments (default: indent=4, sort_keys=True)
    """
    kwargs.setdefault("indent", 4)
    kwargs.setdefault("sort_keys", True)
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp_path = tempfile.mkstemp(
        dir=directory, prefix=".{}.".format(os.path.basename(path)), suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w") as file:
            json.dump(data, file, **kwargs)
            file.flush()
            os.fsync(file.fileno())
        # mkstemp creates the file 0600: keep the mode open() would have given
        os.chmod(tmp_path, _file_mode(path))
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise
    # make the rename itself durable (best effort, not supported everywhere)
    try:
        dir_fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except OSError:
        pass


def set_aside_corrupt_file(cbpi, path, error):
    """
    Called when a config file cannot be loaded. Instead of deleting it, the
    file is renamed to <path>.corrupt-<YYYYmmdd-HHMMSS> so that it can be
    inspected or restored by hand, and the user is notified.

    :param cbpi: craftbeerpi object (used for the notification)
    :param path: file that could not be loaded
    :param error: exception raised while loading
    :return: new path, or None if the file could not be renamed
    """
    from cbpi.api.dataclasses import NotificationType

    name = os.path.basename(path)
    target = "{}.corrupt-{}".format(path, datetime.now().strftime("%Y%m%d-%H%M%S"))
    try:
        os.replace(path, target)
        message = "{} could not be loaded ({}). It was set aside as {} - starting with empty data.".format(
            name, error, target
        )
    except OSError as e:
        target = None
        message = "{} could not be loaded ({}) and could not be set aside ({}) - starting with empty data.".format(
            name, error, e
        )
    logging.error(message)
    try:
        cbpi.notify("Invalid {}".format(name), message, NotificationType.ERROR)
    except Exception as e:
        logging.error("Failed to send notification - {}".format(e))
    return target
