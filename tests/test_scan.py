"""Scan auth-flag construction tests.

scan passes auth options straight through to NetExec. The key regression guard:
``-k`` must appear only when explicitly requested and must never be forced onto
password/hash auth (the old bug that made plain credentialed scans attempt
Kerberos and fail with clock skew).
"""

from aliasr.core.scan import _auth_args, _detect_issue


def test_unauthenticated_is_empty():
    assert _auth_args(None, None, None, False, False) == []


def test_password_auth_is_ntlm_without_kerberos():
    assert _auth_args("alice", "pw", None, False, False) == ["-u", "alice", "-p", "pw"]


def test_hash_auth_is_ntlm_without_kerberos():
    assert _auth_args("alice", None, "DEAD", False, False) == [
        "-u",
        "alice",
        "-H",
        "DEAD",
    ]


def test_password_auth_never_forces_kerberos():
    # Regression: a password/hash scan must not inject -k.
    assert "-k" not in _auth_args("alice", "pw", None, False, False)
    assert "-k" not in _auth_args("alice", None, "DEAD", False, False)


def test_kerberos_with_password_passes_both():
    # -k with creds => nxc requests a TGT using those creds.
    assert _auth_args("alice", "pw", None, True, False) == [
        "-u",
        "alice",
        "-p",
        "pw",
        "-k",
    ]


def test_kerberos_alone_uses_bare_flag():
    assert _auth_args(None, None, None, True, False) == ["-k"]


def test_use_kcache_flag():
    assert _auth_args(None, None, None, False, True) == ["--use-kcache"]


def test_use_kcache_is_not_kerberos_flag():
    # --use-kcache and -k are distinct; -k is only present when requested.
    assert _auth_args(None, None, None, False, True) == ["--use-kcache"]
    assert "-k" not in _auth_args(None, None, None, False, True)


# --- NetExec error surfacing ---

# A failure line as nxc prints it. The password must never reach the user, so
# detection keys off the error code, not the line.
_SKEW_LINE = r"LDAP 10.0.0.1 389 DC01 [-] corp.local\user:S3cretP@ss KRB_AP_ERR_SKEW"


def test_detect_clock_skew():
    msg = _detect_issue(_SKEW_LINE)
    assert msg and "clock skew" in msg.lower()


def test_detect_never_leaks_password():
    # The surfaced hint must not echo the raw credential from the line.
    assert "S3cretP@ss" not in (_detect_issue(_SKEW_LINE) or "")


def test_detect_dns_failure():
    assert _detect_issue("... Name or service not known") is not None


def test_detect_logon_failure():
    msg = _detect_issue(
        r"SMB 10.0.0.1 445 DC01 [-] corp.local\u:p STATUS_LOGON_FAILURE"
    )
    assert msg and "authentication failed" in msg.lower()


def test_detect_benign_line_is_none():
    banner = (
        "SMB 10.0.0.1 445 DC01 [*] Windows Server 2019 (name:DC01) (domain:corp.local)"
    )
    assert _detect_issue(banner) is None
