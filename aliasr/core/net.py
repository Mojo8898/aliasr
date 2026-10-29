"""Local network helpers for seeding the attacker-side globals (``lhost``)."""

import socket

# Interfaces to source ``lhost`` from, in order of preference: the VPN tap into
# the target network first (tun0), then the primary wired NIC (eth0).
LHOST_INTERFACES: tuple[str, ...] = ("tun0", "eth0")

# SIOCGIFADDR: fetch the IPv4 address bound to an interface (Linux ioctl).
_SIOCGIFADDR = 0x8915


def iface_ipv4(name: str) -> str:
    """Return the IPv4 address bound to interface ``name``, or "".

    Uses the SIOCGIFADDR ioctl directly, so there is no subprocess and no
    dependency. Any failure -- a non-Linux platform (no ``fcntl``), a missing
    interface, or one without an IPv4 address -- yields an empty string.
    """
    try:
        import fcntl
        import struct
    except ImportError:
        return ""

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            packed = struct.pack("256s", name[:15].encode("utf-8"))
            res = fcntl.ioctl(s.fileno(), _SIOCGIFADDR, packed)
        return socket.inet_ntoa(res[20:24])
    except OSError:
        return ""


def local_lhost(interfaces: tuple[str, ...] = LHOST_INTERFACES) -> str:
    """Best-guess attacker IP for ``lhost``: the first of ``interfaces`` that
    has an IPv4 address (tun0 preferred, then eth0). Empty when none match."""
    for name in interfaces:
        ip = iface_ipv4(name)
        if ip:
            return ip
    return ""
