#!/usr/bin/env python3
"""Служба FTP сервера Corporate (аналог Services > FTP в Packet Tracer) на pyftpdlib.

Настройки - INI-файл с полями Packet Tracer (Username, Password, права
Write/Read/Delete/Rename/List):
    [ftp]
    service = on
    address = 192.168.1.3
    root = /srv/labnet/Corporate/ftp
    [user Student]
    password = class
    permissions = write, read, delete, rename, list

Права PT переводятся в права pyftpdlib: list -> "el", read -> "r",
write -> "wam", delete -> "d", rename -> "f".

Запуск: python3 ftp_server.py -c ftp.ini [--daemon] [--log FILE] [--pidfile FILE]
"""

import argparse
import configparser
import logging
import os
import select
import sys
import time

PERMS = {"list": "el", "read": "r", "write": "wam", "delete": "d", "rename": "f"}
LOG = logging.getLogger("pyftpdlib")


def load(path):
    cp = configparser.ConfigParser()
    cp.optionxform = str
    if not cp.read(path, encoding="utf-8"):
        raise SystemExit("cannot read config file " + path)
    sec = cp["ftp"]
    cfg = {
        "service": sec.getboolean("service", True),
        "address": sec.get("address", "0.0.0.0").strip(),
        "port": sec.getint("port", 21),
        "root": sec.get("root", "/srv/ftp").strip(),
        "banner": sec.get("banner", "FTP server ready.").strip(),
        "users": [],
    }
    for name in cp.sections():
        if not name.startswith("user "):
            continue
        user = name[5:].strip()
        perm = ""
        for item in cp[name].get("permissions", "read, list").split(","):
            item = item.strip().lower()
            if item not in PERMS:
                raise SystemExit("unknown permission '{}' for user {}".format(item, user))
            for ch in PERMS[item]:
                if ch not in perm:
                    perm += ch
        cfg["users"].append((user, cp[name].get("password", ""), perm))
    return cfg


def build_server(cfg):
    from pyftpdlib.authorizers import DummyAuthorizer
    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import ThreadedFTPServer

    if not cfg["service"]:
        raise RuntimeError("FTP service is off (service = off)")
    authorizer = DummyAuthorizer()
    for user, password, perm in cfg["users"]:
        authorizer.add_user(user, password, cfg["root"], perm=perm)
    handler = FTPHandler
    handler.authorizer = authorizer
    handler.banner = cfg["banner"]
    server = ThreadedFTPServer((cfg["address"], cfg["port"]), handler)
    status = "FTP service is on: {}:{}, root {}, users: {}".format(
        cfg["address"], cfg["port"], cfg["root"],
        ", ".join("{} (perm {})".format(u, p) for u, _, p in cfg["users"]) or "-")
    return server, status


def setup_logging(path, to_stdout):
    handlers = [logging.FileHandler(path)]
    if to_stdout:
        handlers.append(logging.StreamHandler(sys.stdout))
    fmt = logging.Formatter("%(asctime)s %(name)s %(message)s")
    LOG.setLevel(logging.INFO)
    LOG.propagate = False
    for h in handlers:
        h.setFormatter(fmt)
        LOG.addHandler(h)


def main():
    ap = argparse.ArgumentParser(description="FTP service (pyftpdlib)")
    ap.add_argument("-c", "--config", required=True)
    ap.add_argument("--daemon", action="store_true")
    ap.add_argument("--log", default="/var/log/pt-lab/ftp.log")
    ap.add_argument("--pidfile", default=None)
    args = ap.parse_args()
    cfg = load(args.config)
    os.makedirs(os.path.dirname(os.path.abspath(args.log)), exist_ok=True)

    if not args.daemon:
        setup_logging(args.log, True)
        server, status = build_server(cfg)
        print(status, flush=True)
        server.serve_forever()
        return 0

    rfd, wfd = os.pipe()
    pid = os.fork()
    if pid > 0:  # родитель ждёт, пока сервер откроет порт 21
        os.close(wfd)
        data = b""
        deadline = time.time() + 30
        while time.time() < deadline:
            ready, _, _ = select.select([rfd], [], [], max(0.0, deadline - time.time()))
            if not ready:
                break
            chunk = os.read(rfd, 4096)
            if not chunk:
                break
            data += chunk
        text = data.decode("utf-8", "replace").strip()
        if text.startswith("OK "):
            print(text[3:])
            return 0
        print("FTP service failed to start: " + (text or "no status from the service process"), file=sys.stderr)
        return 1

    os.close(rfd)
    os.setsid()
    devnull = os.open(os.devnull, os.O_RDWR)
    for fd in (0, 1, 2):
        os.dup2(devnull, fd)
    setup_logging(args.log, False)
    try:
        server, status = build_server(cfg)
        if args.pidfile:
            with open(args.pidfile, "w") as fh:
                fh.write("{}\n".format(os.getpid()))
    except BaseException as exc:  # noqa: BLE001
        LOG.exception("start failed")
        os.write(wfd, "ERR {}".format(exc).encode("utf-8"))
        os._exit(1)
    LOG.info(status)
    os.write(wfd, ("OK " + status).encode("utf-8"))
    os.close(wfd)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
