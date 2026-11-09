"""Bloqueio de rede no processo dedicado à conversão local."""

import os
import socket
import sys

_installed = False


class OfflineNetworkError(RuntimeError):
    """Uma dependência tentou usar a rede durante uma conversão offline."""


def install_guard():
    global _installed
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
                      HF_HUB_DISABLE_TELEMETRY="1", DO_NOT_TRACK="1")
    if _installed:
        return

    def audit(event, args):
        blocked = event in {"socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr"}
        if event in {"socket.connect", "socket.sendto"}:
            # Pipes e sockets Unix de comunicação entre processos são locais.
            blocked = args[0].family in {socket.AF_INET, socket.AF_INET6}
        if blocked:
            raise OfflineNetworkError("O modo offline bloqueou uma tentativa de acesso à rede. "
                                      "Os modelos devem estar incluídos na instalação. "
                                      "Guarde o relatório para o apoio.")

    sys.addaudithook(audit)
    _installed = True
