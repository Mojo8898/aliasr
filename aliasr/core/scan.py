from __future__ import annotations

import os
import re
import socket
from subprocess import run
from typing import Any


# --------- parsers ---------

_BANNER_NAME = re.compile(r"\(name:([^)]+)\)", re.I)
_BANNER_DOM = re.compile(r"\(domain:([^)]+)\)", re.I)
_SID_LINE = re.compile(r"Domain SID\s+(S-1-[0-9-]+)", re.I)
_ADCS_HOST = re.compile(r"PKI Enrollment Server:\s+(\S+)", re.I)
_ADCS_CN = re.compile(r"Found CN:\s+(.+)", re.I)
_KRB_USER = re.compile(r"\[?\+\]?\s+([^\\]+)\\([^\s]+)\s+from\s+ccache", re.I)


# --------- helpers ---------


def _local_ip_for(ip: str) -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.connect((ip, 1))
        return s.getsockname()[0]


def _run(args: list[str], timeout: float = 12.0) -> list[str]:
    try:
        p = run(args, capture_output=True, text=True, timeout=timeout)
        out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
        return out.splitlines()
    except Exception:
        return []


def _merge_fill(base: dict[str, Any], extra: dict[str, Any]) -> None:
    for k, v in extra.items():
        if v and not base.get(k):
            base[k] = v


# --------- SMB-first fingerprint (no creds) ---------


def _fp_smb(
    ip: str,
    user: str | None = None,
    password: str | None = None,
    nt_hash: str | None = None,
    kerberos: bool = False,
) -> dict[str, Any]:
    res: dict[str, Any] = {
        "Hostname": None,
        "Domain": None,
        "FQDN": None,
        "NetBIOS name": None,
        "User": None,
    }

    # Build command based on auth type
    cmd = ["nxc", "smb", ip]
    if kerberos:
        cmd.append("--use-kcache")
    elif user:
        cmd.extend(["-u", user])
        if password:
            cmd.extend(["-p", password])
        elif nt_hash:
            cmd.extend(["-H", nt_hash])

    for ln in _run(cmd):
        m = _BANNER_NAME.search(ln)
        if m:
            res["Hostname"] = m.group(1).strip()
        m = _BANNER_DOM.search(ln)
        if m:
            res["Domain"] = m.group(1).strip()
        # Try to extract user from Kerberos auth
        if kerberos and not res["User"]:
            m = _KRB_USER.search(ln)
            if m:
                res["User"] = m.group(2).strip()

    if res["Hostname"] and res["Domain"]:
        res["FQDN"] = f"{res['Hostname']}.{res['Domain']}"
    if res["Domain"]:
        res["NetBIOS name"] = res["Domain"].split(".", 1)[0].upper()
    return res


# --------- LDAP fingerprint ---------


def _fp_ldap_banner(ip: str) -> dict[str, Any]:
    res: dict[str, Any] = {"Hostname": None, "Domain": None, "FQDN": None}

    for ln in _run(["nxc", "ldap", ip]):
        m = _BANNER_NAME.search(ln)
        if m:
            res["Hostname"] = m.group(1).strip()
        m = _BANNER_DOM.search(ln)
        if m:
            res["Domain"] = m.group(1).strip()

    if res["Hostname"] and res["Domain"]:
        res["FQDN"] = f"{res['Hostname']}.{res['Domain']}"
    return res


def _fp_ldap(
    ip: str,
    user: str | None = None,
    password: str | None = None,
    nt_hash: str | None = None,
    kerberos: bool = False,
) -> dict[str, Any]:
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

    # Build base command for ADCS module
    cmd_adcs = ["nxc", "ldap", ip, "-M", "adcs"]
    cmd_sid = ["nxc", "ldap", ip, "--get-sid"]

    if kerberos:
        cmd_adcs.append("--use-kcache")
        cmd_sid.append("--use-kcache")
    elif user:
        cmd_adcs.extend(["-u", user])
        cmd_sid.extend(["-u", user])
        if password:
            cmd_adcs.extend(["-p", password])
            cmd_sid.extend(["-p", password])
        elif nt_hash:
            cmd_adcs.extend(["-H", nt_hash])
            cmd_sid.extend(["-H", nt_hash])
        cmd_adcs.append("-k")
        cmd_sid.append("-k")

    else:
        # No valid auth method
        return res

    for ln in _run(cmd_adcs):
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
        # Try to extract user from Kerberos auth
        if kerberos and not res["User"]:
            m = _KRB_USER.search(ln)
            if m:
                res["User"] = m.group(2).strip()

    sid_txt = "\n".join(_run(cmd_sid))
    m_sid = _SID_LINE.search(sid_txt)
    if m_sid:
        res["Domain SID"] = m_sid.group(1)

    # Also check for user in SID output for Kerberos
    if kerberos and not res["User"]:
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
) -> dict[str, Any]:
    """Scan a target and return discovered values as a dict."""
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

    has_auth = bool(user and (password or nt_hash)) or kerberos

    # 1) SMB first
    smb = _fp_smb(ip, user, password, nt_hash, kerberos)

    # Extract user from Kerberos if found
    if kerberos and smb.get("User"):
        vals["user"] = smb["User"]
        user = smb["User"]  # Update for later use

    # 2) LDAP next (if we have auth)
    ldap = _fp_ldap(ip, user, password, nt_hash, kerberos) if has_auth else {}

    # Update user from LDAP if Kerberos and not already found
    if kerberos and not vals["user"] and ldap.get("User"):
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
        ldap_banner = _fp_ldap_banner(ip)

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
) -> int:
    """Execute scan command and update globals."""
    from aliasr.core.globals import load_globals_raw, save_globals
    from aliasr.core.config import GLOBALS_HISTORY
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box

    console = Console()

    # Build scan info display
    scan_info = f"[cyan]Target:[/] {ip}"
    if kerberos:
        scan_info += "\n[cyan]Auth:[/] Kerberos (ccache)"
        if os.environ.get("KRB5CCNAME"):
            scan_info += f"\n[dim]Cache: {os.environ['KRB5CCNAME']}[/]"
    elif user:
        scan_info += f"\n[cyan]User:[/] {user}"
        if password or nt_hash:
            scan_info += " [dim](with credentials)[/]"

    console.print(
        Panel.fit(scan_info, title="[bold]Scanning Target[/]", border_style="cyan")
    )
    console.print()

    # Run the scan
    with console.status("[bold yellow]Scanning...[/]", spinner="dots"):
        results = scan_target(ip, user, password, nt_hash, kerberos)

    # If Kerberos was used and we found a user, update the user variable
    if kerberos and results.get("user"):
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
    console.print()
    console.print("[green]✓[/] Globals updated successfully!")

    return 0
