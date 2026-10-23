from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.fuzzy import Matcher
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static

from aliasr.core.config import kb_root, kb_table_copy
from aliasr.core.creds import Credential, load_creds, save_creds
from aliasr.core.hosts import Host, load_hosts, reconcile_hosts
from aliasr.tui.utils.tables import (
    cred_header,
    cred_option,
    host_header,
    host_option,
    TABLE_BINDINGS,
)
from aliasr.tui.utils.footer import Footer


# Per-tab copy columns: (attribute, human label). Both tabs expose four;
# check_action hides the inactive tab's copy keys from the footer. For hosts,
# "hostname"/"domain" are the short name and domain split out of the stored FQDN.
_COPY_COLS = {
    "creds": {1: ("username", "Username"), 2: ("password", "Password"),
              3: ("hash", "NT Hash"), 4: ("domain", "Domain")},
    "hosts": {1: ("ip", "IP"), 2: ("short_hostname", "Hostname"),
              3: ("domain", "Domain"), 4: ("role", "Role")},
}


class CredsScreen(ModalScreen[None]):
    """Credentials + hosts management screen (two tabs, alt+left/right to switch)."""

    BINDINGS = [
        Binding("escape", "cancel"),
        Binding(kb_root("creds_screen"), "cancel"),

        Binding(kb_root("prev_tab"), "prev_tab", "Prev Tab", tooltip="Switch tab."),
        Binding(kb_root("next_tab"), "next_tab", "Next Tab", tooltip="Switch tab."),

        Binding("up", "list_up"),
        Binding("down", "list_down"),
        Binding("pageup", "list_page_up"),
        Binding("pagedown", "list_page_down"),

        *TABLE_BINDINGS,
        # Credentials copy columns (active on the creds tab).
        Binding(kb_table_copy("col_1"), "copy_user", "Copy User",
                tooltip="Copy the selected username."),
        Binding(kb_table_copy("col_2"), "copy_password", "Copy Password",
                tooltip="Copy the selected password."),
        Binding(kb_table_copy("col_3"), "copy_hash", "Copy Hash",
                tooltip="Copy the selected hash."),
        Binding(kb_table_copy("col_4"), "copy_domain", "Copy Domain",
                tooltip="Copy the selected domain."),
        # Host copy columns (active on the hosts tab).
        Binding(kb_table_copy("col_1"), "copy_ip", "Copy IP",
                tooltip="Copy the selected IP."),
        Binding(kb_table_copy("col_2"), "copy_hostname", "Copy Hostname",
                tooltip="Copy the selected short hostname."),
        Binding(kb_table_copy("col_3"), "copy_host_domain", "Copy Domain",
                tooltip="Copy the selected host's domain."),
        Binding(kb_table_copy("col_4"), "copy_role", "Copy Role",
                tooltip="Copy the selected role."),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._tab: str = "creds"
        self._rows: dict[str, list] = {"creds": [], "hosts": []}
        self._olists: dict[str, OptionList | None] = {"creds": None, "hosts": None}
        self._dirty: dict[str, bool] = {"creds": False, "hosts": False}

    # ---------- UI ----------

    def compose(self) -> ComposeResult:
        with Vertical(id="panel", classes="menu-panel"):
            yield Static(self._tabbar_markup(), id="tabbar")
            yield Input(placeholder="Search... (user/domain, or ip/hostname)", id="filter")
            yield Static(cred_header(), id="creds-head", classes="optionlist-table-header")
            yield OptionList(id="creds-list", classes="optionlist-table")
            yield Static(host_header(), id="hosts-head", classes="optionlist-table-header")
            yield OptionList(id="hosts-list", classes="optionlist-table")
            yield Footer()

    def on_mount(self) -> None:
        self._olists["creds"] = self.query_one("#creds-list", OptionList)
        self._olists["hosts"] = self.query_one("#hosts-list", OptionList)
        for ol in self._olists.values():
            ol.can_focus = False

        try:
            creds = load_creds()
            self._rows["creds"] = list(creds) if creds else [Credential("", "", "", "")]
        except RuntimeError as e:
            self._rows["creds"] = [Credential("Error", str(e), "", "")]
            self._olists["creds"].disabled = True

        try:
            hosts = load_hosts()
            self._rows["hosts"] = list(hosts) if hosts else [Host("", "", "")]
        except RuntimeError as e:
            self._rows["hosts"] = [Host("Error", str(e), "")]
            self._olists["hosts"].disabled = True

        # Remember what was loaded so on close we can tell whether the row
        # backing exegol-history's *current* credential/host was deleted here.
        self._initial_cred_ids = {(c.username, c.domain) for c in self._rows["creds"]}
        self._initial_host_ips = {h.ip for h in self._rows["hosts"] if h.ip}
        self._initial_host_fqdns = {h.hostname for h in self._rows["hosts"] if h.hostname}

        self._populate("creds")
        self._populate("hosts")
        self._show_tab("creds")
        self.query_one("#filter", Input).focus()

    def on_unmount(self) -> None:
        if self._dirty["creds"]:
            survivors = self._non_empty("creds")
            save_creds(survivors)
            self._sync_current_credential(survivors)
            self._dirty["creds"] = False
        if self._dirty["hosts"]:
            survivors = self._non_empty("hosts")
            reconcile_hosts(survivors)
            self._sync_current_host(survivors)
            self._dirty["hosts"] = False

    def _sync_current_credential(self, survivors: list) -> None:
        """Keep exegol-history's profile.sh *current* credential in step with
        edits made here, matching on identity (username, domain):

        * edited in place (password/hash changed) -> rewrite it in profile.sh
        * deleted (identity gone, and it was shown here) -> unset it there,
          mirroring what a bulk `clear creds` already does
        """
        from aliasr.core.exegol import (
            clear_current_credential,
            current_credential,
            set_current_credential,
        )

        cur = current_credential()
        if cur is None:
            return
        ident = (cur.username, cur.domain)
        by_ident = {(c.username, c.domain): c for c in survivors}
        if ident in by_ident:
            match = by_ident[ident]
            if match != cur:  # same account, fields changed -> refresh
                set_current_credential(match)
        elif ident in getattr(self, "_initial_cred_ids", set()):
            clear_current_credential()

    def _sync_current_host(self, survivors: list) -> None:
        """Keep profile.sh's current host in step with edits here. The host is
        matched by ip (exegol/NetExec's key); for the target and the DC
        independently:

        * renamed in place (same ip, new hostname) -> rewrite its fqdn var
        * deleted (its ip, or fqdn for an ip-less host, is gone) -> unset its vars
        """
        from aliasr.core.exegol import current_host, set_current_host

        cur = current_host()
        if not cur:
            return
        by_ip = {h.ip: h for h in survivors if h.ip}
        s_ips = set(by_ip)
        s_fqdns = {h.hostname for h in survivors if h.hostname}
        init_ips = getattr(self, "_initial_host_ips", set())
        init_fqdns = getattr(self, "_initial_host_fqdns", set())

        def _deleted(ip: str, fqdn: str) -> bool:
            ip_gone = bool(ip) and ip in init_ips and ip not in s_ips
            fqdn_gone = bool(fqdn) and fqdn in init_fqdns and fqdn not in s_fqdns
            return ip_gone or (not ip and fqdn_gone)

        t_ip, t_fqdn = cur.get("ip", ""), cur.get("fqdn", "")
        if _deleted(t_ip, t_fqdn):
            set_current_host(ip="", fqdn="")
        elif t_ip in by_ip and by_ip[t_ip].hostname != t_fqdn:
            set_current_host(fqdn=by_ip[t_ip].hostname)

        d_ip, d_fqdn = cur.get("dc_ip", ""), cur.get("dc_fqdn", "")
        if _deleted(d_ip, d_fqdn):
            set_current_host(dc_ip="", dc_fqdn="")
        elif d_ip in by_ip and by_ip[d_ip].hostname != d_fqdn:
            set_current_host(dc_fqdn=by_ip[d_ip].hostname)

    # ---------- Tabs ----------

    def _tabbar_markup(self) -> str:
        tabs = [("creds", "Credentials"), ("hosts", "Hosts")]
        parts = [
            f"[b reverse] {label} [/]" if name == self._tab else f"[dim] {label} [/]"
            for name, label in tabs
        ]
        return "  ".join(parts)

    def _show_tab(self, tab: str) -> None:
        self._tab = tab
        self.query_one("#creds-head").display = tab == "creds"
        self.query_one("#creds-list").display = tab == "creds"
        self.query_one("#hosts-head").display = tab == "hosts"
        self.query_one("#hosts-list").display = tab == "hosts"
        self.query_one("#tabbar", Static).update(self._tabbar_markup())
        self._populate(tab, self.query_one("#filter", Input).value)
        self.refresh_bindings()  # update the footer's copy labels per tab

    def _toggle_tab(self) -> None:
        self._show_tab("hosts" if self._tab == "creds" else "creds")

    # With two tabs prev and next both just toggle; kept as distinct actions so
    # each arrow key has its own binding (and a third tab could differentiate).
    def action_prev_tab(self) -> None:
        self._toggle_tab()

    def action_next_tab(self) -> None:
        self._toggle_tab()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        """Gate the per-tab copy keys.

        The creds and hosts copy actions share keys (ctrl+r/t/y/g). Returning
        ``False`` for the inactive tab's actions drops them from the binding map
        entirely (``None`` would instead keep them, shown greyed, and — since
        the first binding for a key wins — shadow the active tab's labels). With
        ``False`` the active tab's binding takes the key, so the footer shows
        e.g. "Copy IP"/"Copy Hostname" on the hosts tab. Key dispatch still
        falls through to whichever binding is enabled.
        """
        creds_only = {"copy_user", "copy_password", "copy_hash", "copy_domain"}
        hosts_only = {"copy_ip", "copy_hostname", "copy_host_domain", "copy_role"}
        if action in creds_only:
            return self._tab == "creds"
        if action in hosts_only:
            return self._tab == "hosts"
        return True

    # ---------- Helpers ----------

    def _olist(self) -> OptionList | None:
        return self._olists[self._tab]

    def _render_option(self, tab: str, row, idx: int):
        return cred_option(row, idx) if tab == "creds" else host_option(row, idx)

    def _search_text(self, tab: str, row) -> str:
        if tab == "creds":
            return f"{row.username or ''} {row.domain or ''}"
        return f"{row.ip or ''} {row.hostname or ''}"

    def _is_empty(self, tab: str, row) -> bool:
        if tab == "creds":
            return not any((row.username.strip(), row.password, row.hash, row.domain))
        return not any((row.ip.strip(), row.hostname.strip(), row.role.strip()))

    def _empty_row(self, tab: str):
        return Credential("", "", "", "") if tab == "creds" else Host("", "", "")

    def _non_empty(self, tab: str) -> list:
        return [r for r in self._rows[tab] if not self._is_empty(tab, r)]

    def _populate(self, tab: str, query: str = "") -> None:
        ol = self._olists[tab]
        if not ol:
            return
        ol.clear_options()
        rows = self._rows[tab]

        if not query.strip():
            for i, r in enumerate(rows):
                ol.add_option(self._render_option(tab, r, i))
        else:
            m = Matcher(query, case_sensitive=False)
            scored = []
            for i, r in enumerate(rows):
                s = m.match(self._search_text(tab, r))
                if s > 0:
                    scored.append((s, i, r))
            scored.sort(key=lambda t: t[0], reverse=True)
            for _, i, r in scored[:200]:
                ol.add_option(self._render_option(tab, r, i))

        if ol.option_count:
            ol.highlighted = 0

    def _sel_row(self) -> int | None:
        ol = self._olist()
        if ol and ol.highlighted is not None:
            opt = ol.get_option_at_index(ol.highlighted)
            return opt.id if isinstance(opt.id, int) else None
        return None

    def _open_editor(self, row_idx: int) -> None:
        tab = self._tab
        rows = self._rows[tab]
        if not (0 <= row_idx < len(rows)):
            return
        r = rows[row_idx]

        def _done(res) -> None:
            if res is None:
                return
            if tab == "creds":
                u, p, h, d = res
                rows[row_idx] = Credential(u, p, h, d, r.credential_id)
            else:
                ip, hn, role = res
                rows[row_idx] = Host(ip, hn, role, r.host_id)
            self._populate(tab, self.query_one("#filter", Input).value)
            self._dirty[tab] = True

        if tab == "creds":
            from aliasr.tui.creds_screen.cred_editor import CredEditor

            self.app.push_screen(CredEditor(r.username, r.password, r.hash, r.domain), _done)
        else:
            from aliasr.tui.creds_screen.host_editor import HostEditor

            self.app.push_screen(HostEditor(r.ip, r.hostname, r.role), _done)

    def _copy_selected(self, field: str, label: str) -> None:
        r = self._sel_row()
        rows = self._rows[self._tab]
        if r is None or not (0 <= r < len(rows)):
            return
        try:
            from aliasr.core.inject import copy_to_clipboard

            val = getattr(rows[r], field, "") or ""
            if val:
                copy_to_clipboard(val)
                self.notify(f"Copied {label}!", severity="success", timeout=2.5)
        except Exception:
            self.notify("Copy Failed :(", severity="error", timeout=2.5)

    # ---------- Actions ----------

    def action_list_up(self) -> None:
        if self._olist():
            self._olist().action_cursor_up()

    def action_list_down(self) -> None:
        if self._olist():
            self._olist().action_cursor_down()

    def action_list_page_up(self) -> None:
        if self._olist():
            self._olist().action_page_up()

    def action_list_page_down(self) -> None:
        if self._olist():
            self._olist().action_page_down()

    def action_copy_user(self) -> None:
        self._copy_selected("username", "Username")

    def action_copy_password(self) -> None:
        self._copy_selected("password", "Password")

    def action_copy_hash(self) -> None:
        self._copy_selected("hash", "NT Hash")

    def action_copy_domain(self) -> None:
        self._copy_selected("domain", "Domain")

    def action_copy_ip(self) -> None:
        self._copy_selected("ip", "IP")

    def action_copy_hostname(self) -> None:
        self._copy_selected("short_hostname", "Hostname")

    def action_copy_host_domain(self) -> None:
        self._copy_selected("domain", "Domain")

    def action_copy_role(self) -> None:
        self._copy_selected("role", "Role")

    def action_edit_row(self) -> None:
        r = self._sel_row()
        if r is not None:
            self._open_editor(r)

    def action_add_row(self) -> None:
        tab = self._tab

        def _done(res) -> None:
            if res is None:
                return
            if tab == "creds":
                u, p, h, d = res
                self._rows[tab].insert(0, Credential(u, p, h, d))
            else:
                ip, hn, role = res
                self._rows[tab].insert(0, Host(ip, hn, role))
            self._populate(tab, self.query_one("#filter", Input).value)
            self._olists[tab].highlighted = 0
            self._dirty[tab] = True

        if tab == "creds":
            from aliasr.tui.creds_screen.cred_editor import CredEditor

            self.app.push_screen(CredEditor("", "", "", ""), _done)
        else:
            from aliasr.tui.creds_screen.host_editor import HostEditor

            self.app.push_screen(HostEditor("", "", ""), _done)

    def _row_label(self, tab: str, row) -> str:
        if tab == "creds":
            who = row.username or "(no user)"
            return f"credential {who}" + (f"@{row.domain}" if row.domain else "")
        name = row.hostname or row.ip or "(host)"
        return f"host {name}" + (f" ({row.ip})" if row.ip and row.hostname else "")

    def action_delete_row(self) -> None:
        tab = self._tab
        rows = self._rows[tab]
        r = self._sel_row()
        if r is None or not (0 <= r < len(rows)):
            return

        # An empty placeholder row has nothing to lose — delete without asking.
        # The prompt can also be turned off wholesale via [creds] confirm_delete.
        from aliasr.core.config import CREDS_CONFIRM_DELETE

        if self._is_empty(tab, rows[r]) or not CREDS_CONFIRM_DELETE:
            self._do_delete(tab, r)
            return

        from aliasr.tui.creds_screen.confirm import ConfirmDelete

        label = self._row_label(tab, rows[r])

        def _done(ok: bool | None) -> None:
            if ok and 0 <= r < len(self._rows[tab]):
                self._do_delete(tab, r)

        self.app.push_screen(ConfirmDelete(f"Delete {label}?"), _done)

    def _do_delete(self, tab: str, r: int) -> None:
        rows = self._rows[tab]
        ol = self._olists[tab]
        query = self.query_one("#filter", Input).value

        if len(rows) <= 1:
            self._rows[tab] = [self._empty_row(tab)]
            self._populate(tab, query)
            self._dirty[tab] = True
            return

        current_highlight = ol.highlighted
        next_row_idx = r + 1 if r + 1 < len(rows) else r - 1 if r > 0 else None

        rows.pop(r)

        if next_row_idx is not None and next_row_idx > r:
            next_row_idx -= 1

        self._populate(tab, query)

        if next_row_idx is not None and ol.option_count > 0:
            found = False
            for i in range(ol.option_count):
                if ol.get_option_at_index(i).id == next_row_idx:
                    ol.highlighted = i
                    found = True
                    break
            if not found:
                anchor = current_highlight if current_highlight is not None else 0
                ol.highlighted = min(anchor, ol.option_count - 1)
        elif ol.option_count > 0:
            ol.highlighted = 0

        self._dirty[tab] = True

    def action_cancel(self) -> None:
        self.dismiss(None)

    # ---------- Events ----------

    @on(Input.Changed, "#filter")
    def _on_filter(self, e: Input.Changed) -> None:
        self._populate(self._tab, e.value)

    @on(Input.Submitted, "#filter")
    def _submit_filter(self, _: Input.Submitted) -> None:
        r = self._sel_row()
        if r is not None:
            self._open_editor(r)

    @on(OptionList.OptionSelected)
    def _pick_from_list(self, e: OptionList.OptionSelected) -> None:
        if isinstance(e.option.id, int):
            self._open_editor(e.option.id)
        e.stop()
