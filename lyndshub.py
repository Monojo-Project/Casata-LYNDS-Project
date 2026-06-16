#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk, PhotoImage
import platform
import sys
import json
from datetime import datetime
from pathlib import Path
import webbrowser

DATA_ROOT = Path("/usr/local/casata/apps/lyndshub")


def load_json(relative_path: str) -> dict | list:
    full_path = DATA_ROOT / relative_path
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[LyndsHub] WARN: no encontrado → {full_path}")
        return {}
    except json.JSONDecodeError as e:
        print(f"[LyndsHub] ERROR JSON en {full_path}: {e}")
        return {}


# ─────────────────────────────────────────────────────────
#  VALORES RUNTIME DISPONIBLES PARA osinfo.json
# ─────────────────────────────────────────────────────────
def _runtime_values() -> dict:
    u = platform.uname()
    pv = sys.version.split(" ")[0]
    return {
        "os.system":          u.system    or "—",
        "os.node":            u.node      or "—",
        "os.release":         u.release   or "—",
        "os.version":         u.version   or "—",
        "os.machine":         u.machine   or "—",
        "os.processor":       u.processor or platform.processor() or "—",
        "python.version":     pv,
        "python.impl":        platform.python_implementation(),
        "python.compiler":    platform.python_compiler(),
        "python.arch":        " / ".join(platform.architecture()),
        "session.platform":   platform.platform(),
        "session.timestamp":  None,
        "session.app":        None,
        "session.license":    None,
    }


def _load_dynamic_guides() -> dict:
    """Carga todas las guías desde pages/guides/*.json"""
    guides_dir = DATA_ROOT / "pages" / "guides"
    guides = {}

    if not guides_dir.exists():
        return guides

    for json_file in guides_dir.glob("*.json"):
        guide_id = json_file.stem
        guide_data = load_json(f"pages/guides/{json_file.name}")
        if guide_data:
            guides[guide_id] = guide_data
            print(f"[LyndsHub] Guía cargada: {guide_id}")

    return guides


class LyndsHub(tk.Tk):
    def __init__(self):
        super().__init__(className="lyndshub_main")

        cfg     = load_json("config.json")
        fonts   = load_json("fonts.json")
        nav_cfg = load_json("navigation.json")

        app_cfg  = cfg.get("app", {})
        
        # 🔹 ARREGLO DEL MODO OSCURO (Anti-Fogonazos)
        # En chroot el sistema suele estar en UTC. 
        current_hour = datetime.now().hour
        
        # Leemos si has forzado el tema en config.json -> "app": {"theme": "dark"}
        force_theme = app_cfg.get("theme", "auto") 
        base_colors = cfg.get("colors", {})
        
        # Ahora el modo claro dura solo hasta las 20:00 (8 PM)
        is_daytime = 8 <= current_hour < 20
        
        if force_theme == "light" or (force_theme == "auto" and is_daytime):
            # Modo Claro
            self.C = {**base_colors, **cfg.get("colors_light", {})}
        else:

            hacker_dark = {
                "bg": "#0D1117", "sidebar": "#161B22", "text": "#C9D1D9", "text_sub": "#8B949E",
                "card": "#161B22", "card_shadow": "#000000", "border": "#30363D",
                "accent": "#00FF41", "accent_light": "#003300", "sidebar_sel": "#21262D",
                "nav_active_bg": "#003300", "nav_active_fg": "#00FF41"
            }
            self.C = {**base_colors, **hacker_dark, **cfg.get("colors_dark", {})}

        self.F   = fonts.get("fonts", {})
        self.NAV = nav_cfg.get("navigation", [])

        # Cargar config de guías (categorías y colores de dificultad)
        guides_cfg = cfg.get("guides_config", {})
        self.categories = guides_cfg.get("categories", ["Instalación", "Configuración", "Desarrollo", "General"])
        self.diff_colors = guides_cfg.get("difficulty_colors", {
            "principiantes": "#4CAF50", # Verde
            "medios": "#FF9800",        # Naranja
            "profesionales": "#F44336"  # Rojo
        })

        self._name    = app_cfg.get("name",        "")
        self._version = app_cfg.get("version",     "")
        self._desc    = app_cfg.get("description", "")
        self._license = app_cfg.get("license",     "")
        self._copy    = app_cfg.get("copyright",   "")

        win = app_cfg.get("window", {})
        self.title(self._name)
        self.geometry(win.get("size", "1050x680"))
        self.minsize(*win.get("minsize", [900, 600]))
        self.configure(bg=self.C.get("bg", "#FFFFFF"))
        self.resizable(True, True)

        # Usar un tema más limpio para los combobox
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")

        self._current_page = tk.StringVar(value="home")
        self._pages: dict[str, tk.Frame] = {}
        self._guides: dict[str, dict] = _load_dynamic_guides()

        self._build_layout()
        self._show_page("home")


    # ── Helpers ─────────────────────────────────────
    def _f(self, key: str) -> tuple:
        fd     = self.F.get(key, {})
        family = fd.get("family", "TkDefaultFont")
        size   = fd.get("size",   10)
        style  = fd.get("style",  "")
        return (family, size, style) if style else (family, size)

    def _c(self, key_or_hex: str, fallback: str = "#000000") -> str:
        if not key_or_hex:
            return self.C.get(fallback, fallback)
        if key_or_hex.startswith("#"):
            return key_or_hex
        return self.C.get(key_or_hex, fallback)

    def get_colors_key(self, key, fallback):
        return self.C.get(key, fallback)

    # ── Layout & Sidebar ───────────────────────────────────
    def _build_layout(self):
        cfg         = load_json("config.json")
        sidebar_cfg = cfg.get("sidebar", {})
        self.sidebar = tk.Frame(self, bg=self.C["sidebar"], width=sidebar_cfg.get("width", 210))
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)
        self.content = tk.Frame(self, bg=self.C["bg"])
        self.content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._build_sidebar()
        self._build_pages()

    def _build_sidebar(self):
        cfg         = load_json("config.json")
        sidebar_cfg = cfg.get("sidebar", {})

        logo_frame = tk.Frame(self.sidebar, bg=self.C["sidebar"])
        logo_frame.pack(fill=tk.X, padx=sidebar_cfg.get("logo_padx", 20), pady=sidebar_cfg.get("logo_pady", [28, 8]))
        tk.Label(logo_frame, text=sidebar_cfg.get("logo_dot", "●"), fg=self._c(self.C.get("logo_dot", "accent")), bg=self.C["sidebar"], font=self._f("logo_dot")).pack(side=tk.LEFT)
        tk.Label(logo_frame, text=self._name, fg=self._c(self.C.get("logo_text", "text")), bg=self.C["sidebar"], font=self._f("logo")).pack(side=tk.LEFT, padx=(6, 0))

        tk.Frame(self.sidebar, bg=self.C["border"], height=1).pack(fill=tk.X, padx=16, pady=(10, 18))

        ver_bg = self._c(self.C.get("badge_bg", "accent_light"))
        ver_fg = self._c(self.C.get("badge_fg", "accent"))
        ver_frame = tk.Frame(self.sidebar, bg=ver_bg)
        ver_frame.pack(fill=tk.X, padx=16, pady=(0, 18))
        ver_inner = tk.Frame(ver_frame, bg=ver_bg)
        ver_inner.pack(padx=10, pady=6)
        sep = sidebar_cfg.get("version_separator", "  —  ")
        tk.Label(ver_inner, text=f"{self._version}{sep}{self._desc}", fg=ver_fg, bg=ver_bg, font=self._f("small")).pack()

        self._nav_buttons = {}

        for item in self.NAV:
            if item.get("type") == "separator":
                tk.Frame(self.sidebar, bg=self.C["border"], height=1).pack(fill=tk.X, padx=16, pady=10)
                continue
            label = item.get("label")
            page = item.get("page")
            if not page: continue
            btn = self._nav_btn(label, page)
            self._nav_buttons[page] = btn

        if self._guides:
            tk.Frame(self.sidebar, bg=self.C["border"], height=1).pack(fill=tk.X, padx=16, pady=10)
            btn = self._nav_btn("📚 Guías", "guides")
            self._nav_buttons["guides"] = btn

        bottom = tk.Frame(self.sidebar, bg=self.C["sidebar"])
        bottom.pack(side=tk.BOTTOM, fill=tk.X, padx=16, pady=16)
        tk.Frame(bottom, bg=self.C["border"], height=1).pack(fill=tk.X, pady=(0, 10))
        tk.Label(bottom, text=self._copy, fg=self._c(self.get_colors_key("footer_text", "text_sub")), bg=self.C["sidebar"], font=self._f("small")).pack(anchor="w")
        tk.Label(bottom, text=self._license, fg=self._c(self.get_colors_key("footer_license", "accent")), bg=self.C["sidebar"], font=self._f("small")).pack(anchor="w")


    def _nav_btn(self, label: str, page: str) -> tk.Frame:
        container = tk.Frame(self.sidebar, bg=self.C["sidebar"], cursor="hand2")
        container.pack(fill=tk.X, padx=10, pady=2)
        inner = tk.Label(container, text=label, anchor="w",
                         bg=self.C["sidebar"],
                         fg=self._c(self.C.get("nav_text", "text_sub")),
                         font=self._f("nav"), padx=14, pady=9)
        inner.pack(fill=tk.X)

        def on_enter(e):
            if self._current_page.get() != page:
                container.configure(bg=self.C["sidebar_sel"])
                inner.configure(bg=self.C["sidebar_sel"])

        def on_leave(e):
            if self._current_page.get() != page:
                container.configure(bg=self.C["sidebar"])
                inner.configure(bg=self.C["sidebar"])

        def on_click(e):
            self._show_page(page)

        for w in (container, inner):
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            w.bind("<Button-1>", on_click)
        return container

    def _update_nav(self, active: str):
        for page, btn in self._nav_buttons.items():
            inner = btn.winfo_children()[0]
            if page == active:
                btn.configure(bg=self._c(self.C.get("nav_active_bg", "accent_light")))
                inner.configure(bg=self._c(self.get_colors_key("nav_active_bg", "accent_light")),
                                fg=self._c(self.C.get("nav_active_fg", "accent")))
            else:
                btn.configure(bg=self.C["sidebar"])
                inner.configure(bg=self.C["sidebar"],
                                fg=self._c(self.C.get("nav_text", "text_sub")))

    # ── Pages ─────────────────────────────────────────────
    def _build_pages(self):
        builders = {
            "home":      self._page_home,
            "docs":      self._page_docs,
            "osinfo":    self._page_osinfo,
            "credits":   self._page_credits,
            "lyndslite": self._page_lyndslite,
            "guides":    self._page_guides_hub,
        }

        for name, builder in builders.items():
            frame = tk.Frame(self.content, bg=self.C["bg"])
            builder(frame)
            frame.place(relwidth=1, relheight=1)
            self._pages[name] = frame

    def _show_page(self, name: str):
        self._current_page.set(name)
        self._update_nav(name)
        for pname, frame in self._pages.items():
            if pname == name:
                frame.lift()

        if name == "guides" and hasattr(self, "guides_list_frame"):
            self.guides_list_frame.lift()

    # ─────────────────────────────────────────────────────
    #  PAGE: HOME
    # ─────────────────────────────────────────────────────
    def _page_home(self, parent: tk.Frame):
        data = load_json("pages/home.json")
        topbar = data.get("topbar", {})
        self._topbar(parent, topbar.get("title", "Dashboard"), topbar.get("subtitle", ""))

        canvas = tk.Canvas(parent, bg=self.C["bg"], highlightthickness=0)
        scroll = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        body = tk.Frame(canvas, bg=self.C["bg"])
        win = canvas.create_window((0, 0), window=body, anchor="nw")

        def _on_mousewheel(event):
            if event.num == 4: canvas.yview_scroll(-1, "units")
            elif event.num == 5: canvas.yview_scroll(1, "units")
            else: canvas.yview_scroll(int(-1*(event.delta/120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        canvas.bind_all("<Button-4>", _on_mousewheel)
        canvas.bind_all("<Button-5>", _on_mousewheel)

        def _on_configure(e):
            canvas.itemconfig(win, width=e.width)
            canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.bind("<Configure>", _on_configure)

        inner = tk.Frame(body, bg=self.C["bg"])
        inner.pack(fill=tk.BOTH, expand=True, padx=36, pady=20)

        hero_data = data.get("hero", {})
        if hero_data:
            hero = self._card(inner)
            hero._shadow.pack(fill=tk.X, pady=(0, 24))
            tk.Label(hero, text=hero_data.get("title", ""), fg=self.C["accent"], bg=self.C["card"], font=self._f("title")).pack(anchor="w", padx=24, pady=(22, 2))
            tk.Label(hero, text=hero_data.get("description", ""), fg=self.C["text_sub"], bg=self.C["card"], font=self._f("body"), justify="left").pack(anchor="w", padx=24, pady=(0, 10))
            tag_row = tk.Frame(hero, bg=self.C["card"])
            tag_row.pack(anchor="w", padx=24, pady=(0, 22))
            for tag in hero_data.get("tags", []): self._tag(tag_row, tag)

        stats_data = data.get("stats", [])
        if stats_data:
            stats_frame = tk.Frame(inner, bg=self.C["bg"])
            stats_frame.pack(fill=tk.X, pady=(0, 30))
            for col, item in enumerate(stats_data):
                stats_frame.columnconfigure(col, weight=1, uniform="stat")
                c = self._card(stats_frame)
                c._shadow.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 8, 0))
                color = self.C.get(item.get("color", "accent"), item.get("color", "#000"))
                tk.Label(c, text=item.get("value", ""), fg=color, bg=self.C["card"], font=self._f("stat")).pack(pady=(18, 2), padx=20)
                tk.Label(c, text=item.get("label", ""), fg=self.C["text_sub"], bg=self.C["card"], font=self._f("small")).pack(pady=(0, 18), padx=20)

        social_nets = data.get("social_networks", [])
        if social_nets:
            tk.Label(inner, text=data.get("social_section_title", "REDES SOCIALES"), fg=self.C["text"], bg=self.C["bg"], font=self._f("heading")).pack(anchor="w", pady=(10, 15))
            for net in social_nets:
                net_color = net.get("color", self.C["accent"])
                card = self._card(inner)
                card._shadow.pack(fill=tk.X, pady=(0, 16))
                row = tk.Frame(card, bg=self.C["card"], padx=24, pady=18)
                row.pack(fill=tk.X)
                icon_path = DATA_ROOT / net.get("icon_path", "")
                if icon_path.exists():
                    try:
                        img = PhotoImage(file=str(icon_path))
                        if img.width() > 64: img = img.subsample(img.width() // 48)
                        lbl_img = tk.Label(row, image=img, bg=self.C["card"])
                        lbl_img.image = img
                        lbl_img.pack(side=tk.LEFT, padx=(0, 20))
                    except: pass
                tk.Label(row, text=net.get("name", "").upper(), fg=net_color, bg=self.C["card"], font=self._f("title")).pack(side=tk.LEFT)
                btns_frame = tk.Frame(row, bg=self.C["card"])
                btns_frame.pack(side=tk.RIGHT)
                for link in net.get("links", []):
                    l_btn = tk.Label(btns_frame, text=link.get("label", ""), fg="white", bg=net_color, cursor="hand2", font=self._f("small"), padx=16, pady=8)
                    l_btn.pack(side=tk.LEFT, padx=6)
                    url = link.get("url", "#")
                    l_btn.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))

        links_data = data.get("quick_links", [])
        if links_data:
            tk.Label(inner, text=data.get("quick_links_title", "NAVEGACIÓN"), fg=self.C["text"], bg=self.C["bg"], font=self._f("heading")).pack(anchor="w", pady=(20, 15))
            ql_card = self._card(inner)
            ql_card._shadow.pack(fill=tk.X, pady=(0, 40))
            ql_row = tk.Frame(ql_card, bg=self.C["card"], padx=20, pady=20)
            ql_row.pack(fill=tk.X)
            for link in links_data:
                btn = tk.Frame(ql_row, bg=self.C["accent_light"], cursor="hand2", padx=18, pady=12)
                btn.pack(side=tk.LEFT, padx=8, expand=True, fill=tk.X)
                tk.Label(btn, text=link.get("label", ""), fg=self.C["accent"], bg=self.C["accent_light"], font=self._f("subhead")).pack()
                tk.Label(btn, text=link.get("description", ""), fg=self.C["text_sub"], bg=self.C["accent_light"], font=self._f("small")).pack()
                target = link.get("page", "home")
                btn.bind("<Button-1>", lambda e, p=target: self._show_page(p))
                for child in btn.winfo_children():
                    child.bind("<Button-1>", lambda e, p=target: self._show_page(p))

    # ─────────────────────────────────────────────────────
    #  PAGES: DOCS / LYNDSLITE / OSINFO / CREDITS
    # ─────────────────────────────────────────────────────
    def _page_docs(self, parent: tk.Frame):
        data = load_json("pages/docs.json")
        self._build_generic_scrollable_page(parent, data)

    def _page_lyndslite(self, parent: tk.Frame):
        data = load_json("pages/lyndslite.json")
        self._build_generic_scrollable_page(parent, data)

    def _build_generic_scrollable_page(self, parent: tk.Frame, data: dict):
        topbar = data.get("topbar", {})
        self._topbar(parent, topbar.get("title", ""), topbar.get("subtitle", ""))

        canvas = tk.Canvas(parent, bg=self.C["bg"], highlightthickness=0)
        scroll = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(fill=tk.BOTH, expand=True)

        inner = tk.Frame(canvas, bg=self.C["bg"])
        win   = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        inner.bind("<Configure>",  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        def _bind_scroll(e):
            canvas.bind_all("<MouseWheel>", lambda ev: canvas.yview_scroll(-1 * (ev.delta // 120), "units"))
            canvas.bind_all("<Button-4>",   lambda ev: canvas.yview_scroll(-1, "units"))
            canvas.bind_all("<Button-5>",   lambda ev: canvas.yview_scroll( 1, "units"))

        def _unbind_scroll(e):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        canvas.bind("<Enter>", _bind_scroll)
        canvas.bind("<Leave>", _unbind_scroll)
        inner.bind("<Enter>",  _bind_scroll)
        inner.bind("<Leave>",  _unbind_scroll)

        body = tk.Frame(inner, bg=self.C["bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=36, pady=20)

        for section in data.get("sections", []):
            sec = self._card(body)
            sec._shadow.pack(fill=tk.X, pady=(0, 16))
            hdr = tk.Frame(sec, bg=self.C["accent_light"])
            hdr.pack(fill=tk.X)
            tk.Label(hdr, text=section.get("title", ""), fg=self.C["accent"], bg=self.C["accent_light"], font=self._f("heading"), padx=24, pady=12).pack(anchor="w")
            for item in section.get("items", []):
                tk.Label(sec, text=item.get("title", ""), fg=self.C["text"], bg=self.C["card"], font=self._f("subhead"), padx=24).pack(anchor="w", pady=(14, 2))
                tk.Label(sec, text=item.get("text", ""), fg=self.C["text_sub"], bg=self.C["card"], font=self._f("body"), justify="left", wraplength=680, padx=24).pack(anchor="w", pady=(0, 14))

    def _page_osinfo(self, parent: tk.Frame):
        data   = load_json("pages/osinfo.json")
        topbar = data.get("topbar", {})
        self._topbar(parent, topbar.get("title", ""), topbar.get("subtitle", ""))

        body = tk.Frame(parent, bg=self.C["bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=36, pady=20)

        ts_fmt = data.get("timestamp_format", "%Y-%m-%d  %H:%M:%S")
        rv = _runtime_values()
        rv["session.timestamp"] = datetime.now().strftime(ts_fmt)
        rv["session.app"]       = f"{self._name} {self._version}"
        rv["session.license"]   = self._license

        def resolve(val: str) -> str:
            if isinstance(val, str) and val.startswith("$runtime."):
                key = val[len("$runtime."):]
                return rv.get(key, f"[{key} desconocido]")
            return val

        groups = data.get("groups", [])
        left  = tk.Frame(body, bg=self.C["bg"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        right = tk.Frame(body, bg=self.C["bg"])
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(16, 0))

        for i, group in enumerate(groups):
            target = left if i % 2 == 0 else right
            card   = self._card(target)
            card._shadow.pack(fill=tk.X, pady=(0, 16))
            hdr = tk.Frame(card, bg=self.C["accent_light"])
            hdr.pack(fill=tk.X)
            tk.Label(hdr, text=group.get("title", ""), fg=self.C["accent"], bg=self.C["accent_light"], font=self._f("heading"), padx=20, pady=10).pack(anchor="w")
            for row_i, row in enumerate(group.get("rows", [])):
                row_bg = self.C["card"] if row_i % 2 == 0 else self.C["card_shadow"]
                r = tk.Frame(card, bg=row_bg)
                r.pack(fill=tk.X)
                tk.Label(r, text=row.get("key", ""), fg=self.C["text_sub"], bg=row_bg, font=self._f("small"), width=18, anchor="w", padx=20, pady=7).pack(side=tk.LEFT)
                tk.Label(r, text=resolve(row.get("value", "")), fg=self.C["text"], bg=row_bg, font=self._f("mono"), anchor="w").pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 16))

    def _page_credits(self, parent: tk.Frame):
        data   = load_json("pages/credits.json")
        topbar = data.get("topbar", {})
        self._topbar(parent, topbar.get("title", ""), topbar.get("subtitle", ""))

        body = tk.Frame(parent, bg=self.C["bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        team = data.get("team", [])
        if team:
            card_row = tk.Frame(body, bg=self.C["bg"])
            card_row.pack(fill=tk.X, pady=(0, 12))
            for col, member in enumerate(team):
                card_row.columnconfigure(col, weight=1, uniform="member")
                c = self._card(card_row)
                
                c._shadow.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 8, 0))
                
                member_color = self.C.get(member.get("color", "accent"), self.C.get("accent", "#000"))
                av = tk.Frame(c, bg=self.C["card"])
                av.pack(pady=(16, 8))
                tk.Label(av, text=member.get("initial", "?"), fg=self.C.get("avatar_fg", "white"), bg=member_color, font=self._f("avatar"), width=3, height=1).pack(ipadx=8, ipady=8)
                tk.Label(c, text=member.get("name", ""), fg=self.C["text"], bg=self.C["card"], font=self._f("heading")).pack()
                tk.Label(c, text=member.get("role", ""), fg=member_color, bg=self.C["card"], font=self._f("role")).pack(pady=(2, 8))
                
                bio_lbl = tk.Label(c, text=member.get("bio", ""), fg=self.C["text_sub"], bg=self.C["card"], font=self._f("small"), justify="center")
                bio_lbl.pack(padx=10, pady=(0, 10), fill=tk.X)
                bio_lbl.bind("<Configure>", lambda e, w=bio_lbl: w.configure(wraplength=max(50, e.width - 20)))
                
                sf = tk.Frame(c, bg=self.C["card"])
                sf.pack(padx=10, pady=(0, 14))
                for skill in member.get("skills", []): self._tag(sf, skill)

        project = data.get("project", [])
        if project:
            proj = self._card(body)
            proj._shadow.pack(fill=tk.X)
            # Márgenes reducidos en la sección del proyecto
            tk.Label(proj, text=data.get("project_section_title", ""), fg=self.C["text"], bg=self.C["card"], font=self._f("heading")).pack(anchor="w", padx=12, pady=(12, 8))
            info_row = tk.Frame(proj, bg=self.C["card"])
            info_row.pack(fill=tk.X, padx=12, pady=(0, 12))
            for item in project:
                col_f = tk.Frame(info_row, bg=self.C["accent_light"], padx=12, pady=8)
                col_f.pack(side=tk.LEFT, padx=(0, 8))
                tk.Label(col_f, text=item.get("label", ""), fg=self.C["text_sub"], bg=self.C["accent_light"], font=self._f("small")).pack(anchor="w")
                tk.Label(col_f, text=item.get("value", ""), fg=self.C["accent"], bg=self.C["accent_light"], font=self._f("subhead")).pack(anchor="w")


    # ─────────────────────────────────────────────────────
    #  PAGE: GUÍAS HUB (Con Filtros de Dificultad y Categoría)
    # ─────────────────────────────────────────────────────
    def _page_guides_hub(self, parent: tk.Frame):
        self.guides_list_frame = tk.Frame(parent, bg=self.C["bg"])
        self.guides_read_frame = tk.Frame(parent, bg=self.C["bg"])
        self.guides_list_frame.place(relwidth=1, relheight=1)
        self.guides_read_frame.place(relwidth=1, relheight=1)
        self.guides_list_frame.lift()

        # --- VISTA DE BUSCADOR Y LISTA ---
        self._topbar(self.guides_list_frame, "Base de Conocimiento", "Busca y filtra entre todas las guías disponibles")

        search_container = tk.Frame(self.guides_list_frame, bg=self.C["bg"])
        search_container.pack(fill=tk.X, padx=36, pady=(10, 20))

        # 1. Buscador
        search_bg = self.C.get("card", "#f9f9f9")
        search_box = tk.Frame(search_container, bg=search_bg, highlightthickness=1, highlightbackground=self.C["border"])
        search_box.pack(fill=tk.X, pady=(0, 12))

        tk.Label(search_box, text="🔍", bg=search_bg, fg=self.C.get("text_sub")).pack(side=tk.LEFT, padx=(16, 8), pady=12)
        search_var = tk.StringVar()
        entry = tk.Entry(search_box, textvariable=search_var, bg=search_bg, fg=self.C.get("text", "#000"), font=self._f("body"), bd=0, highlightthickness=0)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 16), pady=12)

        # 2. Barra de Filtros (Categoría y Dificultad)
        filters_frame = tk.Frame(search_container, bg=self.C["bg"])
        filters_frame.pack(fill=tk.X)

        # --- Combobox Categoría ---
        tk.Label(filters_frame, text="Categoría:", bg=self.C["bg"], fg=self.C.get("text_sub"), font=self._f("small")).pack(side=tk.LEFT)
        cat_var = tk.StringVar(value="Todas")
        cat_combo = ttk.Combobox(filters_frame, textvariable=cat_var, values=["Todas"] + self.categories, state="readonly", width=15)
        cat_combo.pack(side=tk.LEFT, padx=(5, 20))

        # --- Combobox Dificultad ---
        tk.Label(filters_frame, text="Dificultad:", bg=self.C["bg"], fg=self.C.get("text_sub"), font=self._f("small")).pack(side=tk.LEFT)
        diff_var = tk.StringVar(value="Todas")
        diff_opts = ["Todas", "Principiantes", "Medios", "Profesionales"]
        diff_combo = ttk.Combobox(filters_frame, textvariable=diff_var, values=diff_opts, state="readonly", width=15)
        diff_combo.pack(side=tk.LEFT, padx=(5, 0))

        # 3. Lienzo Scrolleable para resultados
        canvas = tk.Canvas(self.guides_list_frame, bg=self.C["bg"], highlightthickness=0)
        scroll = ttk.Scrollbar(self.guides_list_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(fill=tk.BOTH, expand=True)

        inner = tk.Frame(canvas, bg=self.C["bg"])
        win = canvas.create_window((0, 0), window=inner, anchor="nw")

        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        def _bind_scroll(e):
            canvas.bind_all("<MouseWheel>", lambda ev: canvas.yview_scroll(-1 * (ev.delta // 120), "units"))
            canvas.bind_all("<Button-4>", lambda ev: canvas.yview_scroll(-1, "units"))
            canvas.bind_all("<Button-5>", lambda ev: canvas.yview_scroll(1, "units"))

        def _unbind_scroll(e):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        canvas.bind("<Enter>", _bind_scroll)
        canvas.bind("<Leave>", _unbind_scroll)
        inner.bind("<Enter>", _bind_scroll)
        inner.bind("<Leave>", _unbind_scroll)

        list_body = tk.Frame(inner, bg=self.C["bg"])
        list_body.pack(fill=tk.BOTH, expand=True, padx=36, pady=10)

        def _render_list(*args):
            for widget in list_body.winfo_children():
                widget.destroy()

            query = search_var.get().lower()
            cat_f = cat_var.get().lower()
            diff_f = diff_var.get().lower()

            for g_id, g_data in self._guides.items():
                top = g_data.get("topbar", {})
                title = top.get("title", g_id)
                sub = top.get("subtitle", "")

                # Leemos category y difficulty (Soporta estar en la raíz del json o dentro de 'topbar')
                g_cat = g_data.get("category", top.get("category", "General")).lower()
                g_diff = g_data.get("difficulty", top.get("difficulty", "principiantes")).lower()

                # Filtro de búsqueda por texto
                if query and query not in title.lower() and query not in sub.lower():
                    continue
                # Filtro por Categoría
                if cat_f != "todas" and g_cat != cat_f:
                    continue
                # Filtro por Dificultad
                if diff_f != "todas" and g_diff != diff_f:
                    continue

                card = self._card(list_body)
                card._shadow.pack(fill=tk.X, pady=(0, 14))

                content_frame = tk.Frame(card, bg=self.C["card"], cursor="hand2")
                content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=16)

                tk.Label(content_frame, text=title, fg=self.C["accent"], bg=self.C["card"], font=self._f("subhead"), cursor="hand2").pack(anchor="w")
                if sub:
                    tk.Label(content_frame, text=sub, fg=self.C["text_sub"], bg=self.C["card"], font=self._f("body"), cursor="hand2").pack(anchor="w", pady=(4, 8))

                # Fila de Badges para la tarjeta
                badges_row = tk.Frame(content_frame, bg=self.C["card"], cursor="hand2")
                badges_row.pack(anchor="w", pady=(2, 0))

                # Color de dificultad
                diff_display = g_diff.capitalize()
                diff_color = self.diff_colors.get(g_diff, self.C.get("accent"))
                diff_lbl = self._tag(badges_row, diff_display, bg=diff_color, fg="white")

                # Categoría tag
                cat_lbl = self._tag(badges_row, g_cat.capitalize(), bg=self.C.get("accent_light", "#eee"), fg=self.C.get("accent"))

                def on_click(event, gid=g_id):
                    self._open_guide_view(gid)

                # Hacer que cualquier parte de la tarjeta sea "clickeable"
                click_elements = [card, content_frame, badges_row, diff_lbl, cat_lbl] + content_frame.winfo_children()
                for w in click_elements:
                    try: w.bind("<Button-1>", on_click)
                    except: pass

        # Reactividad
        search_var.trace_add("write", _render_list)
        cat_combo.bind("<<ComboboxSelected>>", _render_list)
        diff_combo.bind("<<ComboboxSelected>>", _render_list)

        _render_list()

    def _open_guide_view(self, guide_id: str):
        """Renderiza la guía completa y muestra sus insignias en la barra superior"""
        for w in self.guides_read_frame.winfo_children():
            w.destroy()

        guide_data = self._guides.get(guide_id, {})

        bar = tk.Frame(self.guides_read_frame, bg=self.C["bg"], height=72)
        bar.pack(fill=tk.X, padx=36, pady=(28, 0))
        bar.pack_propagate(False)

        back_btn = tk.Label(bar, text="← Volver", fg=self.C["text_sub"], bg=self.C["bg"], font=self._f("subhead"), cursor="hand2")
        back_btn.pack(side=tk.LEFT, padx=(0, 16))
        back_btn.bind("<Button-1>", lambda e: self.guides_list_frame.lift())
        back_btn.bind("<Enter>", lambda e: back_btn.configure(fg=self.C["accent"]))
        back_btn.bind("<Leave>", lambda e: back_btn.configure(fg=self.C["text_sub"]))

        top = guide_data.get("topbar", {})
        title = top.get("title", guide_id)
        tk.Label(bar, text=title, fg=self._c(self.C.get("topbar_title", "text")), bg=self.C["bg"], font=self._f("title")).pack(side=tk.LEFT)

        # Añadir insignias a la vista de lectura también
        g_cat = guide_data.get("category", top.get("category", "General")).lower()
        g_diff = guide_data.get("difficulty", top.get("difficulty", "principiantes")).lower()

        tags_row = tk.Frame(bar, bg=self.C["bg"])
        tags_row.pack(side=tk.LEFT, padx=(16, 0), pady=(4, 0))

        diff_color = self.diff_colors.get(g_diff, self.C.get("accent"))
        self._tag(tags_row, g_diff.capitalize(), bg=diff_color, fg="white")
        self._tag(tags_row, g_cat.capitalize(), bg=self.C.get("accent_light", "#eee"), fg=self.C.get("accent"))

        tk.Frame(self.guides_read_frame, bg=self.C["border"], height=1).pack(fill=tk.X, padx=36, pady=(10, 0))

        canvas = tk.Canvas(self.guides_read_frame, bg=self.C["bg"], highlightthickness=0)
        scroll = ttk.Scrollbar(self.guides_read_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(fill=tk.BOTH, expand=True)

        inner = tk.Frame(canvas, bg=self.C["bg"])
        win = canvas.create_window((0, 0), window=inner, anchor="nw")

        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        def _bind_scroll(e):
            canvas.bind_all("<MouseWheel>", lambda ev: canvas.yview_scroll(-1 * (ev.delta // 120), "units"))
            canvas.bind_all("<Button-4>", lambda ev: canvas.yview_scroll(-1, "units"))
            canvas.bind_all("<Button-5>", lambda ev: canvas.yview_scroll(1, "units"))

        def _unbind_scroll(e):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        canvas.bind("<Enter>", _bind_scroll)
        canvas.bind("<Leave>", _unbind_scroll)
        inner.bind("<Enter>", _bind_scroll)
        inner.bind("<Leave>", _unbind_scroll)

        body = tk.Frame(inner, bg=self.C["bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=36, pady=20)

        for block in guide_data.get("blocks", []):
            block_type = block.get("type", "text")
            if block_type == "section": self._render_section(body, block)
            elif block_type == "text": self._render_text(body, block)
            elif block_type == "image": self._render_image(body, block)
            elif block_type == "code": self._render_code(body, block)
            elif block_type == "card": self._render_card_block(body, block)
            elif block_type == "list": self._render_list_block(body, block)

        self.guides_read_frame.lift()

    # ─────────────────────────────────────────────────────
    #  RENDERIZADORES DE BLOQUES DE CONTENIDO
    # ─────────────────────────────────────────────────────
    def _render_section(self, parent: tk.Widget, block: dict):
        frame = tk.Frame(parent, bg=self.C["bg"])
        frame.pack(fill=tk.X, pady=(20, 10))
        title = block.get("title", "")
        subtitle = block.get("subtitle", "")
        tk.Label(frame, text=title, fg=self.C.get("text", "#000"), bg=self.C["bg"], font=self._f("heading")).pack(anchor="w")
        if subtitle:
            tk.Label(frame, text=subtitle, fg=self.C.get("text_sub", "#999"), bg=self.C["bg"], font=self._f("body")).pack(anchor="w", pady=(4, 0))
        
        if "items" in block:
            self._render_list_block(parent, block)

    def _render_text(self, parent: tk.Widget, block: dict):
        text = block.get("content", "")
        font_key = block.get("font", "body")
        color = block.get("color", "text")
        align = block.get("align", "w")
        tk.Label(parent, text=text, fg=self._c(color), bg=self.C["bg"], font=self._f(font_key), wraplength=680, justify="left").pack(anchor=align, padx=0, pady=8)

    def _render_image(self, parent: tk.Widget, block: dict):
        img_path = DATA_ROOT / block.get("src", "")
        if not img_path.exists():
            return
        try:
            img = PhotoImage(file=str(img_path))
            max_width = block.get("width", 600)
            if img.width() > max_width:
                ratio = img.width() / img.height()
                new_height = int(max_width / ratio)
                img = img.subsample(img.width() // max_width)

            frame = tk.Frame(parent, bg=self.C["bg"])
            frame.pack(pady=12)
            img_label = tk.Label(frame, image=img, bg=self.C["bg"])
            img_label.image = img
            img_label.pack()

            caption = block.get("caption", "")
            if caption:
                tk.Label(frame, text=caption, fg=self.C.get("text_sub", "#999"), bg=self.C["bg"], font=self._f("small")).pack(pady=(6, 0))
        except Exception as e:
            print(f"[LyndsHub] ERROR al cargar imagen: {e}")

    def _render_code(self, parent: tk.Widget, block: dict):
        code = block.get("content", "")
        lang = block.get("language", "")

        card = self._card(parent)
        card._shadow.pack(fill=tk.X, pady=12)

        hdr = tk.Frame(card, bg=self.C["accent_light"])
        hdr.pack(fill=tk.X)

        if lang:
            tk.Label(hdr, text=lang.upper(), fg=self.C["accent"], bg=self.C["accent_light"], font=self._f("small"), padx=16, pady=8).pack(side=tk.LEFT, anchor="w")
        else:
            tk.Label(hdr, text="", bg=self.C["accent_light"], pady=8).pack(side=tk.LEFT)

        copy_btn = tk.Label(hdr, text="Copiar", fg=self.C["accent"], bg=self.C["accent_light"], font=self._f("small"), cursor="hand2", padx=16, pady=8)
        copy_btn.pack(side=tk.RIGHT, anchor="e")

        def do_copy(event):
            self.clipboard_clear()
            self.clipboard_append(code)
            copy_btn.configure(text="¡Copiado!")
            self.after(1500, lambda: copy_btn.configure(text="Copiar"))

        copy_btn.bind("<Button-1>", do_copy)
        copy_btn.bind("<Enter>", lambda e: copy_btn.configure(fg=self.C.get("text", "#000")))
        copy_btn.bind("<Leave>", lambda e: copy_btn.configure(fg=self.C["accent"]))

        tk.Label(card, text=code, fg=self.C.get("mono_fg", "#666"), bg=self.C["card"], font=self._f("mono"), justify="left", padx=16, pady=12).pack(anchor="nw", fill=tk.BOTH)

    def _render_card_block(self, parent: tk.Widget, block: dict):
        card = self._card(parent)
        card._shadow.pack(fill=tk.X, pady=12)
        title = block.get("title", "")
        content = block.get("content", "")
        
        # Este es el color de fondo del recuadro (tu verde)
        icon_bg = self.C.get(block.get("icon_color", "accent"), self.C["accent"])
        
        if title:
            hdr = tk.Frame(card, bg=icon_bg)
            hdr.pack(fill=tk.X)
            tk.Label(hdr, text=block.get("icon", "▸") + "  " + title, fg="#000000", bg=icon_bg, font=self._f("subhead"), padx=16, pady=12).pack(anchor="w")
            
        if content:
            # El contenido de abajo lo dejamos con su color normal para que se lea bien en el fondo oscuro
            tk.Label(card, text=content, fg=self.C["text_sub"], bg=self.C["card"], font=self._f("body"), justify="left", wraplength=680, padx=16, pady=12).pack(anchor="nw", fill=tk.BOTH)

    def _render_list_block(self, parent: tk.Widget, block: dict):
        items = block.get("items", [])
        list_type = block.get("list_type", "bullet")
        list_frame = tk.Frame(parent, bg=self.C["bg"])
        list_frame.pack(fill=tk.X, padx=24, pady=8)
        for i, item in enumerate(items):
            item_frame = tk.Frame(list_frame, bg=self.C["bg"])
            item_frame.pack(fill=tk.X, pady=4)
            if list_type == "bullet": symbol = "•"
            elif list_type == "number": symbol = f"{i+1}."
            elif list_type == "check": symbol = "✓"
            else: symbol = "•"
            tk.Label(item_frame, text=symbol, fg=self.C["accent"], bg=self.C["bg"], font=self._f("body"), width=2).pack(side=tk.LEFT)
            tk.Label(item_frame, text=item, fg=self.C["text"], bg=self.C["bg"], font=self._f("body"), wraplength=650, justify="left").pack(side=tk.LEFT, fill=tk.X, expand=True)

    # ─────────────────────────────────────────────────────
    #  HELPERS UI
    # ─────────────────────────────────────────────────────
    def _topbar(self, parent: tk.Frame, title: str, subtitle: str):
        bar = tk.Frame(parent, bg=self.C["bg"], height=72)
        bar.pack(fill=tk.X, padx=36, pady=(28, 0))
        bar.pack_propagate(False)
        tk.Label(bar, text=title, fg=self._c(self.C.get("topbar_title", "text")), bg=self.C["bg"], font=self._f("title")).pack(anchor="w")
        tk.Label(bar, text=subtitle, fg=self._c(self.C.get("topbar_subtitle", "text_sub")), bg=self.C["bg"], font=self._f("body")).pack(anchor="w")
        tk.Frame(parent, bg=self.C["border"], height=1).pack(fill=tk.X, padx=36, pady=(10, 0))

    def _card(self, parent: tk.Widget) -> tk.Frame:
        shadow = tk.Frame(parent, bg=self.C["card_shadow"])
        inner  = tk.Frame(shadow, bg=self.C["card"], highlightthickness=1, highlightbackground=self.C["border"])
        inner.pack(fill=tk.BOTH, expand=True)
        inner._shadow = shadow
        return inner

    def _tag(self, parent: tk.Widget, text: str, bg: str = None, fg: str = None):
        """Retorna el label creado para poder enlazarle eventos si es necesario"""
        lbl = tk.Label(parent, text=text,
                 fg=fg or self.C.get("tag_fg", "#000"),
                 bg=bg or self.C.get("tag_bg", "#eee"),
                 font=self._f("small"), padx=8, pady=3)
        lbl.pack(side=tk.LEFT, padx=(0, 6), pady=2)
        return lbl


if __name__ == "__main__":
    app = LyndsHub()
    app.mainloop()
