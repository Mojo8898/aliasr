import os
import re
import base64
from math import ceil
from pathlib import Path

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid, HorizontalGroup, Vertical
from textual.events import Click
from textual.screen import ModalScreen
from textual.widgets import Footer, Input, OptionList, Static
from textual_autocomplete import DropdownItem, TargetState

from aliasr.core.cheats import get_param_refs
from aliasr.core.config import BUILD_COLUMNS, GLOBALS_AUTO_KRB, kb_build_screen, kb_root
from aliasr.core.globals import get_history, load_globals, save_global
from aliasr.tui.utils.grid_nav import GRID_NAV_BINDINGS, grid_nav
from aliasr.tui.utils.common import widget_id
from aliasr.tui.utils.smart_complete import SmartComplete


PLACEHOLDER_RE = re.compile(r"<([^>\s]+)>")
CRED_PARAMS = {"user", "password", "nt_hash"}


def _apply_tags(cmd: str, tags: frozenset[str]) -> str:
    if "ps_encode" in tags:
        return f"powershell -e {base64.b64encode(cmd.encode('utf-16le')).decode('ascii')}"
    if "sh_encode" in tags:
        return f"echo {base64.b64encode(cmd.encode('utf-8')).decode('ascii')} | base64 -d | /bin/sh"
    return cmd


def _merge_unique(*lists: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for L in lists:
        for s in L or []:
            s = (s or "").strip()
            if s and s not in seen:
                seen.add(s)
                out.append(s)
    return out


class BuildScreen(ModalScreen[str | None]):
    BINDINGS = [
        Binding("escape", "cancel", show=False, priority=True),
        Binding("enter", "submit"),
        *GRID_NAV_BINDINGS,
        Binding("pageup", "sc_page_up"),
        Binding("pagedown", "sc_page_down"),
        Binding(
            kb_build_screen("param_screen"),
            "param_screen",
            "Params",
            tooltip="Open the parameter menu for the currently focused parameter.",
        ),
        Binding(
            kb_root("tree_screen"),
            "tree_screen",
            "Tree",
            tooltip="Open tree menu for the currently focused parameter.",
        ),
    ]

    def __init__(
        self,
        title: str,
        cmd: str,
        md_path: Path,
        tags: frozenset[str] = frozenset(),
        callback=None,
    ) -> None:
        super().__init__()
        self._title = title
        self._cmd = cmd
        self._md_path = md_path
        self._tags = tags
        self._callback = callback

        # Parse parameters and build initial values
        self._params: dict[str, bool] = {}  # {name: is_cred}
        self._values: dict[str, str] = {}  # Current values

        for match in PLACEHOLDER_RE.findall(cmd):
            name, placeholder = match.split("|", 1) if "|" in match else (match, "")

            if name not in self._params:
                self._params[name] = name in CRED_PARAMS

                # Determine initial value with priority
                # if placeholder:
                #     self._values[name] = placeholder
                # else:
                #     refs = get_param_refs(md_path, name)
                #     if refs:
                #         self._values[name] = refs[0]
                #     else:
                #         self._values[name] = self.app.globals.get(name, "")

                first_global = self.app.globals.get(name, "")
                first_reference = (get_param_refs(md_path, name) or [""])[0]
                self._values[name] = first_global or placeholder or first_reference

        # Auto-fill credential parameters with most recent credential
        has_cred_params = any(name in CRED_PARAMS for name in self._params)

        if has_cred_params:
            from aliasr.core.creds import load_creds
            creds = load_creds()

            if creds:
                most_recent = creds[0]
                cred_mapping = {
                    "user": most_recent.username,
                    "password": most_recent.password,
                    "nt_hash": most_recent.hash,
                    "domain": most_recent.domain,
                }

                # Fill any empty credential parameters
                for param_name, cred_value in cred_mapping.items():
                    if param_name in self._params and not self._values.get(param_name) and cred_value:
                        self._values[param_name] = cred_value

        self._preview: Static | None = None
        self._inputs: list[Input] = []
        self._id_to_name: dict[str, str] = {}
        self._refs_cache: dict[str, list[str]] = {}
        self._hist_cache: dict[str, list[str]] = {}

        self._exp_prefix: bool = False
        self._exp_krb: bool = False
        self._krb_global: str = self.app.globals.get("krb5ccname", "")
        self._prefix_global: str = self.app.globals.get("aliasr_prefix", "")

    # ---------- UI ----------

    def compose(self) -> ComposeResult:
        with Vertical(id="panel"):
            tag_str = " ".join(f"#{t}" for t in sorted(self._tags)) if self._tags else ""
            
            with HorizontalGroup(id="title-bar"):
                yield Static(
                    f"{self._title} [{tag_str}]" if tag_str else self._title, id="title"
                )
                
                if self._krb_global:
                    yield Static("krb5ccname? ", id="krb-toggle", classes="toggle-widget")
                    
                if self._prefix_global:
                    yield Static("aliasr_prefix? ", id="prefix-toggle", classes="toggle-widget")

            self._preview = Static(self._cmd, id="preview")
            yield self._preview

            if self._params:
                with Grid(id="grid"):
                    for name, is_cred in self._params.items():
                        inp_id = widget_id("in-", name)
                        inp = Input(placeholder="Enter value...", id=inp_id)
                        inp.border_title = name
                        inp.value = self._values[name]
                        self._id_to_name[inp_id] = name
                        self._inputs.append(inp)
                        yield inp

                for inp in self._inputs:
                    pname = self._id_to_name[inp.id]
                    yield SmartComplete(
                        target=inp,
                        candidates=self._callback_for_param(pname),
                        dropdown_class=f"sc-{pname}",
                        id=widget_id("sc-", inp.id),
                        on_completed=lambda v, p=pname: self._sc_completed(p, v),
                    )
            else:
                yield Static("No parameters to configure - press Enter to continue", id="no-params-message")

            yield Footer()

    def on_mount(self) -> None:
        if self._params:
            grid = self.query_one("#grid", Grid)
            grid.styles.grid_size_columns = BUILD_COLUMNS
            grid.styles.grid_size_rows = self._row_count()

            # Set up caches for refs and history
            for name in self._params.keys():
                self._refs_cache[name] = get_param_refs(self._md_path, name)
                self._hist_cache[name] = get_history(name)

            # Focus first unfilled input or first if all filled
            for inp in self._inputs:
                if not inp.value.strip():
                    inp.focus()
                    inp.action_select_all()
                    break
            else:
                if self._inputs:
                    self._inputs[0].focus()
                    self._inputs[0].action_select_all()
        else:
            self.focus()

        if self._prefix_global:
            self._exp_prefix = True
            self._sync_toggle("prefix")

        krb_env = os.environ.get("KRB5CCNAME") or ""
        if GLOBALS_AUTO_KRB and self._krb_global and self._krb_global != krb_env:
            self._exp_krb = True
            self._sync_toggle("krb")
        else:
            self._exp_krb = False
            self._sync_toggle("krb")

        self._refresh_preview()

    # ---------- Helpers ----------

    def _replace_placeholders(self, cmd: str) -> str:
        """Replace placeholders with values."""
        def repl(m: re.Match[str]) -> str:
            token = m.group(1)
            name = token.split("|", 1)[0]
            return self._values.get(name, "")
        return PLACEHOLDER_RE.sub(repl, cmd)

    def _build_preview(self) -> Text:
        """Build preview text with styled substitutions."""
        text = Text()
        pos = 0
        theme = self.app.available_themes.get(self.app.theme)
        
        for m in PLACEHOLDER_RE.finditer(self._cmd):
            # literal text before placeholder
            if m.start() > pos:
                text.append(self._cmd[pos:m.start()])
            
            # placeholder value
            name = m.group(1).split("|", 1)[0]
            val = self._values.get(name, "")
            if val:
                text.append(val, style=theme.primary)
            # else append nothing for empty
            pos = m.end()
        
        # tail literal
        if self._cmd and pos < len(self._cmd):
            text.append(self._cmd[pos:])
        
        return text

    def _refresh_preview(self) -> None:
        if not self._preview:
            return
        
        theme = self.app.available_themes.get(self.app.theme)
        cmd_preview = self._build_preview()
        text = Text()

        if self._exp_krb:
            text.append(f"export KRB5CCNAME={self._krb_global}; ", style=theme.accent)

        if self._exp_prefix and self._prefix_global:
            if "{cmd}" in self._prefix_global:
                pre, _, post = self._prefix_global.partition("{cmd}")
                if pre:
                    text.append(pre, style=theme.secondary)
                text.append(cmd_preview)
                if post:
                    text.append(post, style=theme.secondary)
            else:
                text.append(self._prefix_global, style=theme.secondary)
                text.append(cmd_preview)
        else:
            text.append(cmd_preview)

        self._preview.update(text)

    def _row_count(self) -> int:
        return 1 if not self._inputs else ceil(len(self._inputs) / BUILD_COLUMNS)

    def _reflect_value(self, name: str) -> None:
        val = self._values.get(name, "")
        for inp in self._inputs:
            if self._id_to_name.get(inp.id) == name:
                if inp.value != val:
                    inp.value = val
                break

    def _sc_completed(self, param: str, value: str) -> None:
        self._values[param] = value
        self._reflect_value(param)
        self._refresh_preview()

    def _callback_for_param(self, param: str):
        def cb(state: TargetState) -> list[DropdownItem]:
            pool = _merge_unique(
                self._refs_cache.get(param, []),
                self._hist_cache.get(param, []),
            )
            q = (state.text or "").lower()
            items = [x for x in pool if q in x.lower()][:30] if q else pool[:30]
            return [DropdownItem(x) for x in items]
        return cb

    def _sync_toggle(self, widget_id: str) -> None:
        try:
            widget = self.query_one(f"#{widget_id}-toggle", Static)
        except Exception:
            return

        if widget_id == "krb":
            enabled = self._exp_krb
            text = f"krb5ccname? {'✓' if enabled else '✗'}"
            widget.set_class(enabled, "enabled")
            widget.set_class(not enabled, "disabled")
        elif widget_id == "prefix":
            enabled = self._exp_prefix
            text = f"aliasr_prefix? {'✓' if enabled else '✗'}"
            widget.set_class(enabled, "enabled")
            widget.set_class(not enabled, "disabled")
        else:
            return

        widget.update(text)
        self._refresh_preview()

    # ---------- Actions ----------

    def action_grid_nav(self, direction: str) -> None:
        if self._inputs:
            grid_nav(
                self,
                direction,
                grid_selector="#grid",
                item_selector="Input",
                cols=BUILD_COLUMNS,
            )

    def action_sc_page_up(self) -> None:
        w = self.focused
        if isinstance(w, Input) and w.id:
            try:
                sc = self.query_one(f"#{widget_id('sc-', w.id)}", SmartComplete)
                if sc.is_dropdown_visible:
                    sc.option_list.action_page_up()
            except Exception:
                pass

    def action_sc_page_down(self) -> None:
        w = self.focused
        if isinstance(w, Input) and w.id:
            try:
                sc = self.query_one(f"#{widget_id('sc-', w.id)}", SmartComplete)
                if sc.is_dropdown_visible:
                    sc.option_list.action_page_down()
            except Exception:
                pass

    def action_param_screen(self) -> None:
        w = self.focused
        if not isinstance(w, Input) or not getattr(w, "id", None):
            return
        param = self._id_to_name.get(w.id)
        if not param:
            return

        refs = get_param_refs(self._md_path, param)
        hist = get_history(param)

        def _done(val):
            if val is None:
                return

            # Handle credential dict return
            if isinstance(val, dict):
                # Update all credential fields that exist in our parameters
                for cred_param in ["user", "password", "nt_hash", "domain"]:
                    if cred_param in self._params and cred_param in val:
                        self._values[cred_param] = val[cred_param]
                        self._reflect_value(cred_param)
            else:
                # Regular string value
                self._values[param] = val
                self._reflect_value(param)

            self._refresh_preview()

            try:
                sc = self.query_one(f"#{widget_id('sc-', w.id)}", SmartComplete)
                sc.action_hide()
            except Exception:
                pass

            self.call_after_refresh(lambda: (w.focus(), w.action_select_all()))

        from aliasr.tui.build_screen.param_screen import ParamScreen
        self.app.push_screen(ParamScreen(param, refs, hist), _done)

    def action_tree_screen(self) -> None:
        w = self.focused
        if not isinstance(w, Input) or not getattr(w, "id", None):
            return
        param = self._id_to_name.get(w.id)
        if not param:
            return

        def _done(result: str | None) -> None:
            if result is None:
                return
            self._values[param] = result
            w.value = result
            self._refresh_preview()

            try:
                sc = self.query_one(f"#{widget_id('sc-', w.id)}", SmartComplete)
                sc.action_hide()
            except Exception:
                pass

            self.call_after_refresh(lambda: (w.focus(), w.action_select_all()))

        from aliasr.tui.tree_screen import TreeScreen
        self.app.push_screen(TreeScreen(), _done)

    def action_submit(self) -> None:
        if isinstance(self.focused, OptionList):
            return

        # Check if we have any true credential values
        cred_values = {k: v for k, v in self._values.items() if k in CRED_PARAMS and v}

        # Save credentials if we have any true cred values
        if cred_values:
            from aliasr.core.creds import Credential, save_creds, load_creds
            new_cred = Credential(
                username=self._values.get("user", ""),
                password=self._values.get("password", ""),
                hash=self._values.get("nt_hash", ""),
                domain=self._values.get("domain", ""),
            )
            existing_creds = load_creds()
            existing_creds.insert(0, new_cred)
            save_creds(existing_creds)

        # Save non-cred parameters to globals (including domain)
        if self._params:
            for name in self._params.keys():
                if name in CRED_PARAMS:
                    continue
                
                val = (self._values.get(name, "") or "").strip()
                if val:
                    save_global(name, val)

            self.app.globals.clear()
            self.app.globals.update(load_globals())

        # Rest of the method...
        built = self._replace_placeholders(self._cmd)
        final_cmd = _apply_tags(built, self._tags)

        if self._exp_prefix and self._prefix_global:
            final_cmd = (
                self._prefix_global.replace("{cmd}", final_cmd)
                if "{cmd}" in self._prefix_global
                else f"{self._prefix_global}{final_cmd}"
            )

        if self._exp_krb and self._krb_global:
            shell = os.environ.get("SHELL", "/bin/sh")
            if "fish" in shell:
                export = f"set -x KRB5CCNAME {self._krb_global}"
            elif "csh" in shell or "tcsh" in shell:
                export = f"setenv KRB5CCNAME {self._krb_global}"
            else:
                export = f"export KRB5CCNAME={self._krb_global}"
            final_cmd = f"{export}; {final_cmd}"
            
            if self.app.in_tmux:
                from aliasr.core.tmux import set_env
                set_env("KRB5CCNAME", self._krb_global)

        self.dismiss(final_cmd)

    def action_cancel(self) -> None:
        self.dismiss(None)

    # ---------- Events ----------

    @on(Input.Changed)
    def _changed(self, event: Input.Changed) -> None:
        name = self._id_to_name.get(event.control.id)
        if not name:
            return
        self._values[name] = event.value
        self._refresh_preview()

    @on(Input.Submitted)
    def _enter(self, event: Input.Submitted) -> None:
        event.stop()
        self.action_submit()

    @on(Click, ".toggle-widget")
    def _toggle_clicked(self, event: Click) -> None:
        if event.control.id == "krb-toggle":
            self._exp_krb = not self._exp_krb
            self._sync_toggle("krb")
        elif event.control.id == "prefix-toggle":
            self._exp_prefix = not self._exp_prefix
            self._sync_toggle("prefix")
