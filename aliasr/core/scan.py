from __future__ import annotations

import os
import re
import shutil
import socket
from subprocess import run, TimeoutExpired
from typing import Any


# --------- parsers ---------

_BANNER_NAME = re.compile(r"\(name:([^)]+)\)", re.I)
_BANNER_DOM = re.compile(r"\(domain:([^)]+)\)", re.I)
_SID_LINE = re.compile(r"Domain SID\s+(S-1-[0-9-]+)", re.I)
_ADCS_HOST = re.compile(r"PKI Enrollment Server:\s+(\S+)", re.I)
_ADCS_CN = re.compile(r"Found CN:\s+(.+)", re.I)
_KRB_USER = re.compile(r"\[?\+\]?\s+([^\\]+)\\([^\s]+)\s+from\s+ccache", re.I)


# --------- error surfacing ---------
#
# NetExec marks a failed probe with a "[-] domain\\user:password <CODE>" line.
# That line contains the password, so we never echo it: we match a known,
# password-free signature and surface a friendly hint instead.

_ISSUE_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"KRB_AP_ERR_SKEW|clock skew", re.I),
     "Kerberos clock skew (KRB_AP_ERR_SKEW): sync your clock to the DC "
     "(e.g. `sudo rdate -n <dc>`, `ntpdate <dc>`, or run under faketime)."),
    (re.compile(r"KDC_ERR_PREAUTH_FAILED", re.I),
     "Kerberos pre-auth failed (KDC_ERR_PREAUTH_FAILED): wrong password or hash."),
    (re.compile(r"KDC_ERR_[CS]_PRINCIPAL_UNKNOWN", re.I),
     "Kerberos principal unknown (KDC_ERR_*_PRINCIPAL_UNKNOWN): check the "
     "username and realm."),
    (re.compile(r"Name or service not known|could not be resolved|getaddrinfo|"
                r"Errno -[0-9]|Temporary failure in name resolution", re.I),
     "DNS resolution failed: the target/DC name couldn't be resolved "
     "(use the FQDN and point your resolver at the DC)."),
    (re.compile(r"STATUS_LOGON_FAILURE", re.I),
     "Authentication failed (STATUS_LOGON_FAILURE): bad username, password, or hash."),
    (re.compile(r"STATUS_ACCOUNT_LOCKED_OUT", re.I),
     "Account locked out (STATUS_ACCOUNT_LOCKED_OUT)."),
    (re.compile(r"STATUS_PASSWORD_EXPIRED|STATUS_PASSWORD_MUST_CHANGE", re.I),
     "Password expired or must be changed for this account."),
    (re.compile(r"STATUS_ACCESS_DENIED", re.I),
     "Access denied (STATUS_ACCESS_DENIED): the account lacks rights for this query."),
    (re.compile(r"Connection (?:refused|reset)|timed out|No route to host|unreachable",
                re.I),
     "Could not reach the target (connection refused / timeout / unreachable)."),
]


def _detect_issue(line: str) -> str | None:
    """Return a friendly, password-free hint if the line names a known error."""
    for rx, msg in _ISSUE_RULES:
        if rx.search(line):
            return msg
    return None


def _add_issue(issues: list[str], msg: str) -> None:
    if msg not in issues:
        issues.append(msg)


# --------- helpers ---------


def _local_ip_for(ip: str) -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect((ip, 1))
            return s.getsockname()[0]
    except OSError:
        return ""


def _run(
    args: list[str],
    issues: list[str] | None = None,
    timeout: float = 12.0,
) -> list[str]:
    try:
        p = run(args, capture_output=True, text=True, timeout=timeout)
        out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
        lines = out.splitlines()
    except TimeoutExpired:
        if issues is not None:
            _add_issue(issues, "A NetExec probe timed out before completing.")
        return []
    except Exception:
        return []

    if issues is not None:
        for ln in lines:
            if "[+]" in ln:  # success line — skip (also avoids scanning creds)
                continue
            msg = _detect_issue(ln)
            if msg:
                _add_issue(issues, msg)
    return lines


def _merge_fill(base: dict[str, Any], extra: dict[str, Any]) -> None:
    for k, v in extra.items():
        if v and not base.get(k):
            base[k] = v


def _auth_args(
    user: str | None,
    password: str | None,
    nt_hash: str | None,
    kerberos: bool,
    use_kcache: bool,
) -> list[str]:
    """Translate the scan's auth options straight into NetExec flags.

    Options map 1:1 onto nxc, so any combination nxc accepts works here. In
    particular ``-k`` is emitted only when explicitly requested — it is never
    forced onto password/hash auth.
    """
    args: list[str] = []
    if user:
        args += ["-u", user]
    if password:
        args += ["-p", password]
    if nt_hash:
        args += ["-H", nt_hash]
    if kerberos:
        args.append("-k")
    if use_kcache:
        args.append("--use-kcache")
    return args


# --------- SMB-first fingerprint (no creds) ---------


def _fp_smb(ip: str, auth: list[str], issues: list[str] | None = None) -> dict[str, Any]:
    res: dict[str, Any] = {
        "Hostname": None,
        "Domain": None,
        "FQDN": None,
        "NetBIOS name": None,
        "User": None,
    }

    for ln in _run(["nxc", "smb", ip, *auth], issues):
        m = _BANNER_NAME.search(ln)
        if m:
            res["Hostname"] = m.group(1).strip()
        m = _BANNER_DOM.search(ln)
        if m:
            res["Domain"] = m.group(1).strip()
        # Pick up the principal when authenticating from a Kerberos ccache
        if not res["User"]:
            m = _KRB_USER.search(ln)
            if m:
                res["User"] = m.group(2).strip()

    if res["Hostname"] and res["Domain"]:
        res["FQDN"] = f"{res['Hostname']}.{res['Domain']}"
    if res["Domain"]:
        res["NetBIOS name"] = res["Domain"].split(".", 1)[0].upper()
    return res


# --------- LDAP fingerprint ---------


def _fp_ldap_banner(ip: str, issues: list[str] | None = None) -> dict[str, Any]:
    res: dict[str, Any] = {"Hostname": None, "Domain": None, "FQDN": None}

    for ln in _run(["nxc", "ldap", ip], issues):
        m = _BANNER_NAME.search(ln)
        if m:
            res["Hostname"] = m.group(1).strip()
        m = _BANNER_DOM.search(ln)
        if m:
            res["Domain"] = m.group(1).strip()

    if res["Hostname"] and res["Domain"]:
        res["FQDN"] = f"{res['Hostname']}.{res['Domain']}"
    return res


def _fp_ldap(ip: str, auth: list[str], issues: list[str] | None = None) -> dict[str, Any]:
    res: dict[str, Any] = {
        "Hostname": None,
        "Domain": None,
        "FQDN": None,
        "NetBIOS name": None,
        "Domain SID": None,
        "CA server": None,
        "CA": None,
        "User": None,
    }

    cmd_adcs = ["nxc", "ldap", ip, "-M", "adcs", *auth]
    cmd_sid = ["nxc", "ldap", ip, "--get-sid", *auth]

    for ln in _run(cmd_adcs, issues):
        m = _BANNER_NAME.search(ln)
        if m:
            res["Hostname"] = m.group(1).strip()
        m = _BANNER_DOM.search(ln)
        if m:
            res["Domain"] = m.group(1).strip()
        if res["CA server"] is None:
            m = _ADCS_HOST.search(ln)
            if m:
                res["CA server"] = m.group(1)
        if res["CA"] is None:
            m = _ADCS_CN.search(ln)
            if m:
                res["CA"] = m.group(1).strip()
        # Pick up the principal when authenticating from a Kerberos ccache
        if not res["User"]:
            m = _KRB_USER.search(ln)
            if m:
                res["User"] = m.group(2).strip()

    sid_txt = "\n".join(_run(cmd_sid, issues))
    m_sid = _SID_LINE.search(sid_txt)
    if m_sid:
        res["Domain SID"] = m_sid.group(1)

    # Also check for the principal in the SID output
    if not res["User"]:
        m = _KRB_USER.search(sid_txt)
        if m:
            res["User"] = m.group(2).strip()

    if res["Hostname"] and res["Domain"]:
        res["FQDN"] = f"{res['Hostname']}.{res['Domain']}"
    if res["Domain"]:
        res["NetBIOS name"] = res["Domain"].split(".", 1)[0].upper()
    return res


# --------- scanning logic ---------


def scan_target(
    ip: str,
    user: str | None = None,
    password: str | None = None,
    nt_hash: str | None = None,
    kerberos: bool = False,
    use_kcache: bool = False,
    issues: list[str] | None = None,
) -> dict[str, Any]:
    """Scan a target and return discovered values as a dict.

    Any NetExec problems detected during the scan (clock skew, DNS failures,
    bad credentials, ...) are appended to ``issues`` when a list is supplied.
    """
    if issues is None:
        issues = []
    vals: dict[str, Any] = {
        "lhost": _local_ip_for(ip),
        "ip": ip,
        "dc_ip": "",
        "user": user or "",
        "hostname": None,
        "domain": None,
        "fqdn": None,
        "dc_fqdn": "",
        "domain_sid": None,
        "ca": None,
        "ca_fqdn": None,
        "netbios": None,
        "tld": None,
    }

    auth = _auth_args(user, password, nt_hash, kerberos, use_kcache)
    # LDAP ADCS/SID lookups need real authentication; a bare -u is not enough.
    has_auth = bool(password or nt_hash or kerberos or use_kcache)

    # 1) SMB first
    smb = _fp_smb(ip, auth, issues)

    # Pick up the principal discovered via a Kerberos ccache
    if not vals["user"] and smb.get("User"):
        vals["user"] = smb["User"]

    # 2) LDAP next (if we have auth)
    ldap = _fp_ldap(ip, auth, issues) if has_auth else {}

    # Fill the principal from LDAP if SMB didn't surface it
    if not vals["user"] and ldap.get("User"):
        vals["user"] = ldap["User"]

    # merge: keep SMB values, fill missing from LDAP
    merged: dict[str, Any] = {
        "Hostname": smb.get("Hostname"),
        "Domain": smb.get("Domain"),
        "FQDN": smb.get("FQDN"),
        "NetBIOS name": smb.get("NetBIOS name"),
        "Domain SID": None,
        "CA server": None,
        "CA": None,
    }
    _merge_fill(merged, ldap)

    # map to requested globals
    vals["hostname"] = merged.get("Hostname")
    vals["domain"] = merged.get("Domain")
    vals["fqdn"] = merged.get("FQDN")
    vals["domain_sid"] = merged.get("Domain SID")
    vals["ca"] = merged.get("CA")
    vals["ca_fqdn"] = merged.get("CA server")
    vals["netbios"] = merged.get("NetBIOS name")

    domain = (vals["domain"] or "").strip(".")
    vals["tld"] = domain.rsplit(".", 1)[-1].lower() if "." in domain else ""

    # DC detection: prefer authenticated LDAP, otherwise (or as fallback) use unauth LDAP banner
    ldap_banner = {}
    if not ldap.get("Domain"):
        # banner fallback both unauthenticated and when auth LDAP didn't return domain
        ldap_banner = _fp_ldap_banner(ip, issues)

    # Require a real domain signal (and ideally an fqdn/hostname) before calling it a DC
    dc_domain = ldap.get("Domain") or ldap_banner.get("Domain")
    dc_fqdn = ldap.get("FQDN") or ldap_banner.get("FQDN") or ""

    is_dc = bool(dc_domain and (dc_fqdn or (ldap_banner.get("Hostname") and dc_domain)))

    if is_dc:
        vals["dc_ip"] = ip
        vals["dc_fqdn"] = dc_fqdn or vals.get("fqdn") or ""

    # Clean up None values to empty strings for consistency
    for k in vals:
        if vals[k] is None:
            vals[k] = ""

    return vals


# --------- CLI command handler ---------


def run_scan_cli(
    ip: str,
    user: str | None = None,
    password: str | None = None,
    nt_hash: str | None = None,
    kerberos: bool = False,
    use_kcache: bool = False,
) -> int:
    """Execute scan command and update globals."""
    from aliasr.core.globals import load_globals_raw, save_globals
    from aliasr.core.config import GLOBALS_HISTORY
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box

    console = Console()

    if shutil.which("nxc") is None:
        console.print(
            "[red]✗ NetExec ('nxc') was not found on PATH.[/] "
            "Install it to use [bold]aliasr scan[/]."
        )
        return 1

    # Build scan info display
    scan_info = f"[cyan]Target:[/] {ip}"
    if user:
        scan_info += f"\n[cyan]User:[/] {user}"
    auth_bits = []
    if password:
        auth_bits.append("password")
    if nt_hash:
        auth_bits.append("NT hash")
    if kerberos:
        auth_bits.append("kerberos")
    if use_kcache:
        auth_bits.append("ccache")
    if auth_bits:
        scan_info += f"\n[cyan]Auth:[/] {', '.join(auth_bits)}"
    if use_kcache and os.environ.get("KRB5CCNAME"):
        scan_info += f"\n[dim]Cache: {os.environ['KRB5CCNAME']}[/]"

    console.print(
        Panel.fit(scan_info, title="[bold]Scanning Target[/]", border_style="cyan")
    )
    console.print()

    # Run the scan
    issues: list[str] = []
    with console.status("[bold yellow]Scanning...[/]", spinner="dots"):
        results = scan_target(
            ip, user, password, nt_hash, kerberos, use_kcache, issues
        )

    # If we discovered the principal (e.g. from a ccache), use it for creds
    if results.get("user"):
        user = results["user"]

    # Prepare the payload for merging with globals
    raw_globals = load_globals_raw()
    payload = {}

    for key, value in results.items():
        # Skip "user" - it should only be in credentials, not globals
        if key == "user":
            continue

        # Convert value to string, handling None and empty values
        str_value = str(value) if value is not None else ""

        # Get existing history for this key
        existing = raw_globals.get(key, [])

        # Only update if we have a non-empty value
        if str_value:
            if GLOBALS_HISTORY:
                # With history: prepend the new value to the list
                if isinstance(existing, list):
                    # Remove duplicates and prepend new value
                    filtered = [v for v in existing if v != str_value]
                    payload[key] = [str_value] + filtered
                else:
                    # Convert single value to list
                    payload[key] = (
                        [str_value, str(existing)]
                        if existing and str(existing) != str_value
                        else [str_value]
                    )
            else:
                # Without history: just replace with new value
                payload[key] = [str_value]
        # If value is empty but key exists in globals, preserve existing (don't add empty)
        # We don't add this key to payload, which means it won't be modified

    # Save the merged globals
    save_globals(payload)

    # Save credentials if provided (password or NT hash)
    if user and (password or nt_hash):
        from aliasr.core.creds import Credential, load_creds, save_creds

        # Get discovered domain
        discovered_domain = results.get("domain", "")

        # Load existing credentials
        existing_creds = load_creds() or []

        # Check if this credential already exists
        found = False
        for i, cred in enumerate(existing_creds):
            if (
                cred.username == user
                and (
                    (password and cred.password == password)
                    or (nt_hash and cred.hash == nt_hash)
                )
                and cred.domain == discovered_domain
            ):
                found = True
                break

        # If not found, add as a new credential
        if not found:
            new_cred = Credential(
                username=user,
                password=password or "",
                hash=nt_hash or "",  # Use provided hash or empty
                domain=discovered_domain,
            )
            existing_creds.insert(0, new_cred)
            save_creds(existing_creds)

            auth_type = "password" if password else "NT hash"
            console.print(
                f"[green]✓[/] Saved credentials for {user}@{discovered_domain or '<no domain>'} ({auth_type})"
            )

    # Display results in specified order
    table = Table(
        show_header=True, title="[bold green]Scan Results[/]", box=box.ROUNDED
    )
    table.add_column("Global", style="cyan", no_wrap=True)
    table.add_column("Value", style="yellow")

    # Define the display order
    display_order = [
        "lhost",
        "ip",
        "hostname",
        "domain",
        "fqdn",
        "dc_ip",
        "dc_fqdn",
        "domain_sid",
        "ca",
        "ca_fqdn",
        "netbios",
        "tld",
    ]

    # Display in the specified order
    for key in display_order:
        if key in results:
            value = results[key]
            display_value = str(value) if value else "[dim]<empty>[/]"
            table.add_row(key, display_value)

    console.print(table)

    if issues:
        console.print()
        console.print(
            Panel.fit(
                "\n".join(f"[yellow]⚠[/]  {m}" for m in issues),
                title="[bold yellow]Warnings[/]",
                border_style="yellow",
            )
        )

    console.print()
    if issues:
        console.print(
            "[yellow]⚠  Globals updated, but some lookups failed "
            "(see warnings above).[/]"
        )
    else:
        console.print("[green]✓[/] Globals updated successfully!")

    return 0
