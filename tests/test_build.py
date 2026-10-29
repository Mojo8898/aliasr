"""Tests for aliasr.core.build — the shared non-interactive command builder."""

import pytest

from aliasr.core import build


class TestFillPlaceholders:
    def test_value_wins(self):
        assert build.fill_placeholders("u <user>", {"user": "bob"}) == "u bob"

    def test_default_used_when_absent(self):
        assert build.fill_placeholders("n <name|test>", {}) == "n test"

    def test_present_empty_value_wins_over_default(self):
        # An explicit clear beats the token default.
        assert build.fill_placeholders("n <name|test>", {"name": ""}) == "n "

    def test_missing_is_empty_when_lenient(self):
        assert build.fill_placeholders("x <gone>", {}) == "x "

    def test_missing_raises_when_strict(self):
        with pytest.raises(build.BuildError, match="unbound"):
            build.fill_placeholders("x <gone>", {}, strict=True)


class TestApplyEncodeTags:
    def test_ps_encode(self):
        out = build.apply_encode_tags("whoami", frozenset({"ps_encode"}))
        assert out.startswith("powershell -e ")

    def test_sh_encode(self):
        out = build.apply_encode_tags("id", frozenset({"sh_encode"}))
        assert out.startswith("echo ") and "base64 -d | /bin/sh" in out

    def test_no_tag_passthrough(self):
        assert build.apply_encode_tags("id", frozenset()) == "id"


class TestSkewTarget:
    def test_none_without_faketime(self):
        assert build.skew_target(frozenset(), {"ip": "1.2.3.4"}) is None

    def test_prefers_ip(self):
        assert (
            build.skew_target(frozenset({"faketime"}), {"ip": "1.2.3.4"}) == "1.2.3.4"
        )

    def test_falls_back_to_dc_ip_then_fallback(self):
        assert (
            build.skew_target(frozenset({"faketime"}), {"dc_ip": "5.6.7.8"})
            == "5.6.7.8"
        )
        assert (
            build.skew_target(frozenset({"faketime"}), {}, fallback="9.9.9.9")
            == "9.9.9.9"
        )


class TestRender:
    def test_single_command_bare(self):
        assert build.render("whoami <ip>", {"ip": "1.2.3.4"}) == "whoami 1.2.3.4"

    def test_multi_command_arun_chain(self):
        out = build.render("mkdir x\nls <ip>", {"ip": "1.2.3.4"})
        assert out == "arun mkdir x ; \\\narun ls 1.2.3.4"

    def test_selections_expanded_per_head(self):
        cmd = "nxc smb <ip> <auth>\nsmbclientng --host <fqdn> <auth>"
        out = build.render(
            cmd, {"ip": "1.2.3.4", "fqdn": "dc.d"}, selections={"auth": "Kerberos"}
        )
        assert "arun nxc smb 1.2.3.4 --use-kcache" in out
        assert "arun smbclientng --host dc.d --ccache-file $KRB5CCNAME" in out

    def test_faketime_exports_skew(self):
        out = build.render(
            "getTGT.py <domain>\nnxc ldap <ip>",
            {"domain": "d.htb", "ip": "1.2.3.4"},
            build_tags=frozenset({"faketime"}),
        )
        assert out.startswith("export AR_SKEW=1.2.3.4 ; \\\n")
        assert "arun getTGT.py d.htb" in out

    def test_target_local_emits_bare(self):
        out = build.render("whoami\nhostname", {}, cheat_tags=("target/local",))
        assert "arun" not in out
        assert out == "whoami ; \\\nhostname"

    def test_ps_encode_skips_arun_chain(self):
        out = build.render("whoami\nhostname", {}, build_tags=frozenset({"ps_encode"}))
        assert out.startswith("powershell -e ")
        assert "arun" not in out

    def test_prefix_prepended_per_command(self):
        out = build.render("a\nb", {}, prefix="proxychains ")
        assert out == "arun proxychains a ; \\\narun proxychains b"

    def test_strict_raises_on_unbound(self):
        with pytest.raises(build.BuildError):
            build.render("nxc <ip> <missing>", {"ip": "1.2.3.4"}, strict=True)
