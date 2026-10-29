"""Tests for the attacker-interface helper that seeds the ``lhost`` global."""

from aliasr.core import net


def test_local_lhost_prefers_tun0(monkeypatch):
    ips = {"tun0": "10.10.14.9", "eth0": "192.168.1.5"}
    monkeypatch.setattr(net, "iface_ipv4", lambda name: ips.get(name, ""))
    assert net.local_lhost() == "10.10.14.9"


def test_local_lhost_falls_back_to_eth0(monkeypatch):
    ips = {"tun0": "", "eth0": "192.168.1.5"}
    monkeypatch.setattr(net, "iface_ipv4", lambda name: ips.get(name, ""))
    assert net.local_lhost() == "192.168.1.5"


def test_local_lhost_empty_when_no_interface(monkeypatch):
    monkeypatch.setattr(net, "iface_ipv4", lambda name: "")
    assert net.local_lhost() == ""


def test_local_lhost_respects_interface_order(monkeypatch):
    monkeypatch.setattr(
        net, "iface_ipv4", lambda name: "1.2.3.4" if name == "wlan0" else ""
    )
    assert net.local_lhost(("tun0", "eth0")) == ""
    assert net.local_lhost(("wlan0",)) == "1.2.3.4"
