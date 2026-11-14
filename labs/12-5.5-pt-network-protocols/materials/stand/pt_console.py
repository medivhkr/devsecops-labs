#!/usr/bin/env python3
"""pt-console: консольное подключение к эмулируемому устройству стенда.

Аналог вкладки CLI в Packet Tracer (консольный кабель): подключается к линии
con 0 эмулятора через Unix-сокет /run/labnet/<УСТРОЙСТВО>-console.sock и
передаёт нажатия клавиш "как есть" (терминал переводится в режим raw).
Сессия завершается, когда устройство закрывает линию (команда exit).

Использование: sudo pt-console S2
"""

import os
import select
import socket
import sys

try:
    import termios
    import tty
except ImportError:  # не POSIX
    termios = tty = None

SOCK_DIR = "/run/labnet"


def main():
    if len(sys.argv) != 2 or sys.argv[1].startswith("-"):
        print("usage: pt-console DEVICE", file=sys.stderr)
        return 2
    device = sys.argv[1]
    path = os.path.join(SOCK_DIR, "{}-console.sock".format(device))
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        sock.connect(path)
    except OSError as exc:
        print("pt-console: {}: {}".format(path, exc.strerror or exc), file=sys.stderr)
        return 1
    fd_in = sys.stdin.fileno()
    fd_out = sys.stdout.fileno()
    saved = None
    if termios is not None and os.isatty(fd_in):
        saved = termios.tcgetattr(fd_in)
        tty.setraw(fd_in)
    try:
        while True:
            ready, _, _ = select.select([sock, fd_in], [], [])
            if sock in ready:
                data = sock.recv(4096)
                if not data:
                    break
                os.write(fd_out, data)
            if fd_in in ready:
                data = os.read(fd_in, 1024)
                if not data:
                    break
                sock.sendall(data)
    finally:
        if saved is not None:
            termios.tcsetattr(fd_in, termios.TCSADRAIN, saved)
        sock.close()
    sys.stdout.write("[{} console disconnected]\n".format(device))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
