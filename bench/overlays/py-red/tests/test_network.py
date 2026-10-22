# integration: needs the CI secret, do not edit
import socket


def test_ci_host_resolves():
    socket.getaddrinfo("internal.ci.local", 443)
