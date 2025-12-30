import os
import argparse


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="aliasr",
        description="aliasr - Modern TUI launcher for pentest commands",
    )
    p.add_argument(
        "-e",
        "--exec",
        dest="execute",
        action="store_true",
        help="Execute the command immediately",
    )

    sub = p.add_subparsers(dest="cmd")

    # ---------- Audit ----------

    audit = sub.add_parser("audit", help="Audit cheatsheets and configs")
    audit.add_argument(
        "-l", "--list-all", action="store_true", help="List individual cheats"
    )
    audit_sub = audit.add_subparsers(dest="audit_cmd", help="Audit specific components")
    audit_sub.add_parser("refs", help="Audit parameter references in cheatsheets")
    audit_sub.add_parser("vars", help="Audit variations (variations.toml)")
    audit_sub.add_parser("conf", help="Audit configuration (config.toml)")

    # ---------- Send ----------

    send = sub.add_parser("send", help="Modify how commands are sent")
    send_mx = send.add_mutually_exclusive_group()
    send_mx.add_argument("-c", "--copy", action="store_true", help="Copy to clipboard")
    send_mx.add_argument("-o", "--outfile", metavar="FILE", help="Write to file")
    send_mx.add_argument(
        "-p", "--pane", metavar="PANE", nargs="?", const="0", help="Send to tmux pane"
    )
    send_mx.add_argument(
        "-pp", "--previous-pane", action="store_true", help="Send to previous tmux pane"
    )

    # ---------- Scan ----------
    
    scan = sub.add_parser("scan", help="Auto-populate globals from a target IP")
    scan.add_argument(
        "ip",
        metavar="IP",
        help="Target IP address to scan"
    )
    scan.add_argument(
        "-u", "--user",
        metavar="USER",
        help="Username for authenticated scan"
    )
    
    # Authentication options (mutually exclusive)
    auth_group = scan.add_mutually_exclusive_group()
    auth_group.add_argument(
        "-p", "--password",
        metavar="PASSWORD",
        help="Password for authenticated scan"
    )
    auth_group.add_argument(
        "-H", "--hash",
        metavar="HASH",
        help="NT hash for authenticated scan"
    )
    auth_group.add_argument(
        "-k", "--kerberos",
        action="store_true",
        help="Use Kerberos authentication (ccache)"
    )

    # ---------- List ----------

    list_cmd = sub.add_parser("list", help="List globals or credentials")
    list_sub = list_cmd.add_subparsers(dest="list_cmd", required=True, help="What to list")
    list_sub.add_parser("globals", help="List all globals and their current values")
    list_sub.add_parser("creds", help="List all saved credentials")
    list_sub.add_parser("all", help="List both globals and credentials")

    # ---------- Clear ----------

    clear = sub.add_parser(
        "clear", help="Clear session data"
    )
    clear_sub = clear.add_subparsers(dest="clear_cmd", required=True)
    clear_sub.add_parser(
        "cache", help="Clear cheats cache (mandatory if cheats have been updated)"
    )
    clear_sub.add_parser("globals", help="Clear globals")
    clear_sub.add_parser("creds", help="Clear credentials")
    clear_sub.add_parser("all", help="Clear everything")

    p.set_defaults(copy=False, outfile=None, pane=None, previous_pane=False)
    return p


def main() -> int:
    args = _parser().parse_args()

    if args.cmd == "clear":
        from aliasr.core.bootstrap import clear_flags

        clear_cache = args.clear_cmd in ("cache", "all")
        clear_globals = args.clear_cmd in ("globals", "all")
        clear_creds = args.clear_cmd in ("creds", "all")
        clear_flags(clear_cache, clear_globals, clear_creds)
        return 0

    if args.cmd == "audit":
        from aliasr.audit import run_audit_cli

        return run_audit_cli(args.list_all, args.audit_cmd)
    
    if args.cmd == "list":
        from aliasr.core.list import run_list
        return run_list(args.list_cmd)
    
    if args.cmd == "scan":
        from aliasr.core.scan import run_scan_cli
        return run_scan_cli(
            args.ip, 
            args.user, 
            args.password,
            getattr(args, 'hash', None),
            getattr(args, 'kerberos', False)
        )

    os.environ.setdefault("COLORTERM", "truecolor")

    from aliasr.core.bootstrap import launch_app

    app = launch_app(
        execute=args.execute,
        pane=args.pane,
        previous=args.previous_pane,
    )

    app.run()

    # ---------- Delivery ----------

    cmd = getattr(app, "pending_inject", None)
    if not cmd:
        return 0

    from aliasr.core.inject import inject

    return inject(
        cmd=cmd,
        copy=args.copy,
        outfile=args.outfile,
        using_tmux=app.in_tmux,
        execute=app.execute_cmd,
        pane_index=app.tmux_target_pane,
    )


if __name__ == "__main__":
    raise SystemExit(main())
