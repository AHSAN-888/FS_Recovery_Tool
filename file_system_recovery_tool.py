"""
File System Recovery and Optimization Tool
CSE-316 CA2 | Ahsan Muhammed | Roll: 12414232 | R424GBB60
Problem #53 — File System Recovery and Optimization Tool

Requirements: Python 3.x (no extra installs needed — uses only stdlib)
Run: python file_system_recovery_tool.py
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import random
import time
import threading
import struct
import hashlib
import json
import os
from datetime import datetime
from collections import OrderedDict

# ─────────────────────────────────────────────
#  DATA STRUCTURES
# ─────────────────────────────────────────────

class BTreeNode:
    def __init__(self, leaf=True):
        self.keys   = []
        self.values = []
        self.children = []
        self.leaf = leaf

class BTree:
    """Minimal B-Tree for O(log n) file lookups."""
    def __init__(self, t=2):
        self.root = BTreeNode()
        self.t = t

    def insert(self, key, value):
        r = self.root
        if len(r.keys) == 2 * self.t - 1:
            s = BTreeNode(leaf=False)
            s.children.append(self.root)
            self._split_child(s, 0)
            self.root = s
        self._insert_non_full(self.root, key, value)

    def _insert_non_full(self, node, key, value):
        i = len(node.keys) - 1
        if node.leaf:
            node.keys.append(None)
            node.values.append(None)
            while i >= 0 and key < node.keys[i]:
                node.keys[i+1] = node.keys[i]
                node.values[i+1] = node.values[i]
                i -= 1
            node.keys[i+1] = key
            node.values[i+1] = value
        else:
            while i >= 0 and key < node.keys[i]:
                i -= 1
            i += 1
            if len(node.children[i].keys) == 2 * self.t - 1:
                self._split_child(node, i)
                if key > node.keys[i]:
                    i += 1
            self._insert_non_full(node.children[i], key, value)

    def _split_child(self, parent, i):
        t = self.t
        y = parent.children[i]
        z = BTreeNode(leaf=y.leaf)
        parent.keys.insert(i, y.keys[t-1])
        parent.values.insert(i, y.values[t-1])
        parent.children.insert(i+1, z)
        z.keys   = y.keys[t:]
        z.values = y.values[t:]
        y.keys   = y.keys[:t-1]
        y.values = y.values[:t-1]
        if not y.leaf:
            z.children = y.children[t:]
            y.children = y.children[:t]

    def search(self, key, node=None):
        node = node or self.root
        i = 0
        while i < len(node.keys) and key > node.keys[i]:
            i += 1
        if i < len(node.keys) and key == node.keys[i]:
            return node.values[i]
        if node.leaf:
            return None
        return self.search(key, node.children[i])

    def traverse(self, node=None, result=None):
        node = node or self.root
        result = result if result is not None else []
        for i, k in enumerate(node.keys):
            if not node.leaf:
                self.traverse(node.children[i], result)
            result.append(k)
        if not node.leaf:
            self.traverse(node.children[-1], result)
        return result


class LRUCache:
    """LRU Cache backed by OrderedDict."""
    def __init__(self, capacity=4):
        self.capacity = capacity
        self.cache = OrderedDict()

    def get(self, key):
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key, value):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

    def snapshot(self):
        return list(reversed(list(self.cache.items())))


# ─────────────────────────────────────────────
#  VIRTUAL DISK
# ─────────────────────────────────────────────

SECTOR_COUNT  = 512
SECTOR_SIZE   = 128   # bytes (simulated)

STATUS_FREE      = 0
STATUS_USED      = 1
STATUS_CORRUPTED = 2
STATUS_RECOVERED = 3
STATUS_BAD       = 4

STATUS_COLORS = {
    STATUS_FREE:      "#d0f0c0",
    STATUS_USED:      "#4a90d9",
    STATUS_CORRUPTED: "#e74c3c",
    STATUS_RECOVERED: "#27ae60",
    STATUS_BAD:       "#95a5a6",
}

FILE_SIGNATURES = {
    "pdf":  bytes([0x25, 0x50, 0x44, 0x46]),
    "jpg":  bytes([0xFF, 0xD8, 0xFF, 0xE0]),
    "txt":  bytes([0xEF, 0xBB, 0xBF, 0x00]),
    "mp4":  bytes([0x00, 0x00, 0x00, 0x18]),
    "docx": bytes([0x50, 0x4B, 0x03, 0x04]),
}


class VirtualDisk:
    def __init__(self):
        self.sectors = [STATUS_FREE] * SECTOR_COUNT
        self.files   = []        # list of dicts
        self.journal = []        # write-ahead log

    # ── helpers ──────────────────────────────
    def free_sectors(self):
        return [i for i, s in enumerate(self.sectors) if s == STATUS_FREE]

    def allocate(self, count):
        free = self.free_sectors()
        if len(free) < count:
            return None
        start = free[random.randint(0, max(0, len(free) - count))]
        allocated = list(range(start, min(start + count, SECTOR_COUNT)))
        for s in allocated:
            self.sectors[s] = STATUS_USED
        return allocated

    # ── Module 1: Disk Simulator ──────────────
    def write_file(self, name, ftype):
        sizes = {"pdf":(80,400),"jpg":(120,800),"txt":(4,50),"mp4":(2000,8000),"docx":(40,200)}
        mn, mx = sizes.get(ftype, (50, 300))
        size_kb = random.randint(mn, mx)
        sector_count = max(2, size_kb // (SECTOR_SIZE // 1024 + 1))
        allocated = self.allocate(sector_count)
        if allocated is None:
            return None, "Not enough free sectors"
        checksum = hashlib.md5(f"{name}{ftype}{time.time()}".encode()).hexdigest()[:8].upper()
        entry = dict(
            name=name, ftype=ftype, size_kb=size_kb,
            sectors=allocated, status="ok", checksum=checksum
        )
        self.files.append(entry)
        # journal entry
        self.journal.append(dict(
            ts=datetime.now().strftime("%H:%M:%S"),
            event="WRITE", filename=f"{name}.{ftype}",
            sectors=f"{allocated[0]}-{allocated[-1]}",
            checksum=checksum, data=dict(entry)
        ))
        return entry, None

    def simulate_crash(self, mode="random"):
        events = []
        if mode == "random":
            n = random.randint(10, 40)
            corrupted = 0
            for _ in range(n):
                idx = random.randint(0, SECTOR_COUNT - 1)
                if self.sectors[idx] == STATUS_USED:
                    self.sectors[idx] = STATUS_CORRUPTED
                    corrupted += 1
            for f in self.files:
                if any(self.sectors[s] == STATUS_CORRUPTED for s in f["sectors"]):
                    if f["status"] == "ok":
                        f["status"] = "corrupt"
            events.append(f"Random crash: {corrupted} sectors corrupted")
        elif mode == "power":
            if not self.files:
                return ["No files to corrupt"]
            victim = random.choice(self.files)
            half = len(victim["sectors"]) // 2
            for s in victim["sectors"][:half]:
                self.sectors[s] = STATUS_CORRUPTED
            victim["status"] = "corrupt"
            events.append(f"Power failure: partial write of {victim['name']}.{victim['ftype']}")
        elif mode == "bad":
            n = random.randint(5, 20)
            marked = 0
            for _ in range(n):
                idx = random.randint(0, SECTOR_COUNT - 1)
                if self.sectors[idx] == STATUS_FREE:
                    self.sectors[idx] = STATUS_BAD
                    marked += 1
            events.append(f"Bad blocks: {marked} sectors marked unreadable")
        self.journal.append(dict(
            ts=datetime.now().strftime("%H:%M:%S"),
            event="CRASH", mode=mode, description=events[0]
        ))
        return events

    def reset(self):
        self.sectors = [STATUS_FREE] * SECTOR_COUNT
        self.files   = []
        self.journal = []

    # ── Module 2: Recovery ────────────────────
    def scan_signatures(self):
        results = []
        for f in self.files:
            if f["status"] == "corrupt":
                sig = FILE_SIGNATURES.get(f["ftype"], b"\xDE\xAD\xBE\xEF")
                hex_sig = sig.hex().upper()
                results.append((f, hex_sig, f["sectors"][0]))
        return results

    def recover_journal(self):
        recovered, failed = [], []
        for f in list(self.files):
            if f["status"] != "corrupt":
                continue
            j_entry = next((j for j in self.journal
                            if j.get("event") == "WRITE"
                            and j.get("filename") == f"{f['name']}.{f['ftype']}"), None)
            if j_entry and random.random() > 0.25:
                f["status"] = "recovered"
                for s in f["sectors"]:
                    if self.sectors[s] == STATUS_CORRUPTED:
                        self.sectors[s] = STATUS_RECOVERED
                recovered.append(f)
            else:
                failed.append(f)
        return recovered, failed

    def recover_all(self):
        recovered, lost = [], []
        for f in self.files:
            if f["status"] != "corrupt":
                continue
            if random.random() > 0.15:
                f["status"] = "recovered"
                for s in f["sectors"]:
                    if self.sectors[s] == STATUS_CORRUPTED:
                        self.sectors[s] = STATUS_RECOVERED
                recovered.append(f)
            else:
                f["status"] = "lost"
                lost.append(f)
        return recovered, lost

    # ── Module 3: Optimizer ───────────────────
    def benchmark(self, optimization="none"):
        base_read  = random.uniform(40, 55)
        base_write = random.uniform(35, 48)
        multipliers = {
            "none":  (1.0, 1.0),
            "btree": (2.8, 1.4),
            "lru":   (3.5, 1.2),
            "both":  (5.2, 2.1),
        }
        rm, wm = multipliers.get(optimization, (1.0, 1.0))
        return round(base_read * rm, 1), round(base_write * wm, 1)

    def defragment(self):
        """Rearrange used sectors contiguously."""
        used_files = [f for f in self.files if f["status"] in ("ok","recovered")]
        self.sectors = [STATUS_FREE] * SECTOR_COUNT
        ptr = 0
        for f in used_files:
            count = len(f["sectors"])
            f["sectors"] = list(range(ptr, ptr + count))
            for s in f["sectors"]:
                self.sectors[s] = STATUS_USED
            ptr += count
        return len(used_files)


# ─────────────────────────────────────────────
#  GUI
# ─────────────────────────────────────────────

COLORS = {
    "bg":       "#1e1e2e",
    "surface":  "#2a2a3e",
    "accent":   "#7f77dd",
    "green":    "#27ae60",
    "red":      "#e74c3c",
    "blue":     "#3498db",
    "amber":    "#f39c12",
    "text":     "#ecf0f1",
    "muted":    "#8e9aaf",
    "border":   "#3d3d5c",
}

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("File System Recovery & Optimization Tool — CSE-316 CA2")
        self.configure(bg=COLORS["bg"])
        self.geometry("1100x780")
        self.resizable(True, True)

        self.disk = VirtualDisk()
        self.btree = BTree()
        self.lru   = LRUCache(capacity=4)
        self.bench_results = []

        self._build_ui()
        self._log(self.log1, "Virtual disk initialized — 512 sectors (64 MB simulated)", "ok")
        self._log(self.log1, "FAT table ready | Journal logging active", "info")
        self._log(self.log2, "Recovery engine ready — waiting for crash event...", "info")
        self._log(self.log3, "Optimizer ready — run a benchmark to begin", "info")
        self._render_disk()

    # ── UI Construction ───────────────────────
    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=COLORS["surface"], pady=8)
        hdr.pack(fill=tk.X, padx=10, pady=(10,0))
        self.status_dot = tk.Label(hdr, text="●", fg=COLORS["green"], bg=COLORS["surface"], font=("Courier",14))
        self.status_dot.pack(side=tk.LEFT, padx=(12,6))
        tk.Label(hdr, text="File System Recovery & Optimization Tool",
                 fg=COLORS["text"], bg=COLORS["surface"],
                 font=("Courier",13,"bold")).pack(side=tk.LEFT)
        self.status_lbl = tk.Label(hdr, text="System nominal — disk mounted",
                                   fg=COLORS["muted"], bg=COLORS["surface"], font=("Courier",10))
        self.status_lbl.pack(side=tk.RIGHT, padx=12)

        # Notebook
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook", background=COLORS["bg"], borderwidth=0)
        style.configure("TNotebook.Tab", background=COLORS["surface"],
                        foreground=COLORS["muted"], font=("Courier",10),
                        padding=[14,6])
        style.map("TNotebook.Tab",
                  background=[("selected", COLORS["accent"])],
                  foreground=[("selected", "white")])

        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.tab1 = tk.Frame(nb, bg=COLORS["bg"])
        self.tab2 = tk.Frame(nb, bg=COLORS["bg"])
        self.tab3 = tk.Frame(nb, bg=COLORS["bg"])
        nb.add(self.tab1, text=" Module 1 — Disk Simulator ")
        nb.add(self.tab2, text=" Module 2 — Recovery Engine ")
        nb.add(self.tab3, text=" Module 3 — Optimizer ")

        self._build_tab1()
        self._build_tab2()
        self._build_tab3()

    # ── TAB 1 ──────────────────────────────────
    def _build_tab1(self):
        p = self.tab1

        # Stats row
        srow = tk.Frame(p, bg=COLORS["bg"])
        srow.pack(fill=tk.X, padx=8, pady=8)
        self.lbl_total   = self._stat_card(srow, "Total Sectors", "512")
        self.lbl_used    = self._stat_card(srow, "Used Sectors",  "0")
        self.lbl_free    = self._stat_card(srow, "Free Sectors",  "512")
        self.lbl_corrupt = self._stat_card(srow, "Corrupted",     "0")

        # Disk canvas
        canv_frame = tk.LabelFrame(p, text="  Virtual Disk — Sector Map  ",
                                   fg=COLORS["accent"], bg=COLORS["surface"],
                                   font=("Courier",10), bd=1, relief=tk.FLAT)
        canv_frame.pack(fill=tk.X, padx=8, pady=4)
        self.disk_canvas = tk.Canvas(canv_frame, bg=COLORS["surface"],
                                     height=120, highlightthickness=0)
        self.disk_canvas.pack(fill=tk.X, padx=4, pady=4)

        # Legend
        leg = tk.Frame(canv_frame, bg=COLORS["surface"])
        leg.pack(fill=tk.X, padx=4, pady=(0,6))
        for label, color in [("Free","#d0f0c0"),("Used","#4a90d9"),
                              ("Corrupted","#e74c3c"),("Recovered","#27ae60"),
                              ("Bad Block","#95a5a6")]:
            tk.Label(leg, text="■", fg=color, bg=COLORS["surface"],
                     font=("Courier",11)).pack(side=tk.LEFT, padx=2)
            tk.Label(leg, text=label, fg=COLORS["muted"], bg=COLORS["surface"],
                     font=("Courier",9)).pack(side=tk.LEFT, padx=(0,10))

        # Progress bars
        pb_frame = tk.Frame(p, bg=COLORS["bg"])
        pb_frame.pack(fill=tk.X, padx=8, pady=4)
        tk.Label(pb_frame, text="Disk Usage:", fg=COLORS["muted"],
                 bg=COLORS["bg"], font=("Courier",10), width=14, anchor="w").grid(row=0,column=0,padx=4)
        self.usage_pb = ttk.Progressbar(pb_frame, length=400, mode="determinate")
        self.usage_pb.grid(row=0,column=1,padx=4)
        self.usage_pct = tk.Label(pb_frame, text="0%", fg=COLORS["text"],
                                  bg=COLORS["bg"], font=("Courier",10), width=6)
        self.usage_pct.grid(row=0,column=2)
        tk.Label(pb_frame, text="Corruption:", fg=COLORS["muted"],
                 bg=COLORS["bg"], font=("Courier",10), width=14, anchor="w").grid(row=1,column=0,padx=4,pady=4)
        self.corrupt_pb = ttk.Progressbar(pb_frame, length=400, mode="determinate",
                                           style="red.Horizontal.TProgressbar")
        self.corrupt_pb.grid(row=1,column=1,padx=4)
        self.corrupt_pct = tk.Label(pb_frame, text="0%", fg=COLORS["red"],
                                    bg=COLORS["bg"], font=("Courier",10), width=6)
        self.corrupt_pct.grid(row=1,column=2)

        # Controls
        ctrl = tk.Frame(p, bg=COLORS["bg"])
        ctrl.pack(fill=tk.X, padx=8, pady=4)
        tk.Label(ctrl, text="Filename:", fg=COLORS["muted"],
                 bg=COLORS["bg"], font=("Courier",10)).pack(side=tk.LEFT, padx=4)
        self.fname_var = tk.StringVar(value="report")
        tk.Entry(ctrl, textvariable=self.fname_var, width=16,
                 bg=COLORS["surface"], fg=COLORS["text"],
                 insertbackground=COLORS["text"], font=("Courier",10),
                 relief=tk.FLAT, bd=4).pack(side=tk.LEFT, padx=4)
        tk.Label(ctrl, text="Type:", fg=COLORS["muted"],
                 bg=COLORS["bg"], font=("Courier",10)).pack(side=tk.LEFT)
        self.ftype_var = tk.StringVar(value="pdf")
        ttk.Combobox(ctrl, textvariable=self.ftype_var,
                     values=["pdf","jpg","txt","mp4","docx"],
                     width=6, font=("Courier",10), state="readonly").pack(side=tk.LEFT, padx=4)
        self._btn(ctrl, "Write File", self._write_file, COLORS["green"]).pack(side=tk.LEFT, padx=4)

        crash_row = tk.Frame(p, bg=COLORS["bg"])
        crash_row.pack(fill=tk.X, padx=8, pady=2)
        self._btn(crash_row, "Simulate Crash (Random)",  lambda: self._crash("random"), COLORS["red"]).pack(side=tk.LEFT, padx=4)
        self._btn(crash_row, "Power Failure",            lambda: self._crash("power"),  COLORS["red"]).pack(side=tk.LEFT, padx=4)
        self._btn(crash_row, "Mark Bad Blocks",          lambda: self._crash("bad"),    COLORS["amber"]).pack(side=tk.LEFT, padx=4)
        self._btn(crash_row, "Reset Disk",               self._reset_disk,              COLORS["muted"]).pack(side=tk.LEFT, padx=4)

        self.log1 = self._log_box(p)

    # ── TAB 2 ──────────────────────────────────
    def _build_tab2(self):
        p = self.tab2

        srow = tk.Frame(p, bg=COLORS["bg"])
        srow.pack(fill=tk.X, padx=8, pady=8)
        self.lbl_r_corrupt   = self._stat_card(srow, "Corrupted Files",  "0")
        self.lbl_r_recovered = self._stat_card(srow, "Recovered Files",  "0")
        self.lbl_r_lost      = self._stat_card(srow, "Unrecoverable",    "0")

        # File table
        ft_frame = tk.LabelFrame(p, text="  File Allocation Table  ",
                                  fg=COLORS["accent"], bg=COLORS["surface"],
                                  font=("Courier",10), bd=1, relief=tk.FLAT)
        ft_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        cols = ("Name","Type","Size","Sectors","Status","Checksum")
        self.file_tree = ttk.Treeview(ft_frame, columns=cols, show="headings", height=8)
        widths = [120,60,80,120,90,110]
        for col, w in zip(cols, widths):
            self.file_tree.heading(col, text=col)
            self.file_tree.column(col, width=w, anchor="center")
        self.file_tree.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # Progress
        self.recovery_pb  = ttk.Progressbar(p, length=600, mode="determinate")
        self.recovery_pb.pack(padx=8, pady=4)
        self.recovery_lbl = tk.Label(p, text="", fg=COLORS["muted"],
                                     bg=COLORS["bg"], font=("Courier",10))
        self.recovery_lbl.pack()

        # Buttons
        btn_row = tk.Frame(p, bg=COLORS["bg"])
        btn_row.pack(pady=4)
        self._btn(btn_row, "Scan Disk (Signatures)", self._scan_signatures, COLORS["blue"]).pack(side=tk.LEFT, padx=4)
        self._btn(btn_row, "Recover via Journal",    self._recover_journal,  COLORS["blue"]).pack(side=tk.LEFT, padx=4)
        self._btn(btn_row, "Recover All",            self._recover_all,      COLORS["green"]).pack(side=tk.LEFT, padx=4)

        self.log2 = self._log_box(p, height=8)

    # ── TAB 3 ──────────────────────────────────
    def _build_tab3(self):
        p = self.tab3

        srow = tk.Frame(p, bg=COLORS["bg"])
        srow.pack(fill=tk.X, padx=8, pady=8)
        self.lbl_read  = self._stat_card(srow, "Read Speed",  "0 MB/s")
        self.lbl_write = self._stat_card(srow, "Write Speed", "0 MB/s")
        self.lbl_speedup = self._stat_card(srow, "Speedup",   "1.0×")

        # Chart
        chart_frame = tk.LabelFrame(p, text="  Performance Benchmark  ",
                                    fg=COLORS["accent"], bg=COLORS["surface"],
                                    font=("Courier",10), bd=1, relief=tk.FLAT)
        chart_frame.pack(fill=tk.X, padx=8, pady=4)
        self.chart_canvas = tk.Canvas(chart_frame, bg=COLORS["surface"],
                                      height=180, highlightthickness=0)
        self.chart_canvas.pack(fill=tk.X, padx=4, pady=4)

        # Buttons
        btn_row = tk.Frame(p, bg=COLORS["bg"])
        btn_row.pack(pady=4)
        self._btn(btn_row, "No Optimization",   lambda: self._benchmark("none"),  COLORS["red"]).pack(side=tk.LEFT, padx=4)
        self._btn(btn_row, "B-Tree Index",       lambda: self._benchmark("btree"), COLORS["blue"]).pack(side=tk.LEFT, padx=4)
        self._btn(btn_row, "LRU Cache",          lambda: self._benchmark("lru"),   COLORS["blue"]).pack(side=tk.LEFT, padx=4)
        self._btn(btn_row, "B-Tree + LRU + Defrag", lambda: self._benchmark("both"), COLORS["green"]).pack(side=tk.LEFT, padx=4)

        # B-Tree & LRU display
        ds_frame = tk.Frame(p, bg=COLORS["bg"])
        ds_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        bt_lf = tk.LabelFrame(ds_frame, text="  B-Tree Index  ",
                               fg=COLORS["accent"], bg=COLORS["surface"],
                               font=("Courier",10), bd=1, relief=tk.FLAT)
        bt_lf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,4))
        self.btree_canvas = tk.Canvas(bt_lf, bg=COLORS["surface"],
                                      height=100, highlightthickness=0)
        self.btree_canvas.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        lru_lf = tk.LabelFrame(ds_frame, text="  LRU Cache (4 slots)  ",
                                fg=COLORS["accent"], bg=COLORS["surface"],
                                font=("Courier",10), bd=1, relief=tk.FLAT)
        lru_lf.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(4,0))
        self.lru_canvas = tk.Canvas(lru_lf, bg=COLORS["surface"],
                                    height=100, highlightthickness=0)
        self.lru_canvas.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.log3 = self._log_box(p, height=6)

    # ── Helpers ───────────────────────────────
    def _stat_card(self, parent, label, value):
        f = tk.Frame(parent, bg=COLORS["surface"], relief=tk.FLAT, bd=1)
        f.pack(side=tk.LEFT, padx=6, pady=4, ipadx=14, ipady=6)
        tk.Label(f, text=label, fg=COLORS["muted"],
                 bg=COLORS["surface"], font=("Courier",9)).pack()
        lbl = tk.Label(f, text=value, fg=COLORS["text"],
                       bg=COLORS["surface"], font=("Courier",16,"bold"))
        lbl.pack()
        return lbl

    def _btn(self, parent, text, cmd, color):
        return tk.Button(parent, text=text, command=cmd,
                         bg=COLORS["surface"], fg=color,
                         activebackground=COLORS["border"],
                         font=("Courier",10), relief=tk.FLAT,
                         bd=1, cursor="hand2", padx=8, pady=4)

    def _log_box(self, parent, height=7):
        f = tk.Frame(parent, bg=COLORS["surface"])
        f.pack(fill=tk.X, padx=8, pady=4)
        log = scrolledtext.ScrolledText(f, height=height, bg=COLORS["surface"],
                                        fg=COLORS["text"], font=("Courier",9),
                                        relief=tk.FLAT, insertbackground=COLORS["text"])
        log.pack(fill=tk.X)
        log.tag_config("ok",   foreground=COLORS["green"])
        log.tag_config("err",  foreground=COLORS["red"])
        log.tag_config("warn", foreground=COLORS["amber"])
        log.tag_config("info", foreground=COLORS["blue"])
        return log

    def _log(self, widget, msg, tag=""):
        ts = datetime.now().strftime("%H:%M:%S")
        widget.insert(tk.END, f"[{ts}] {msg}\n", tag)
        widget.see(tk.END)

    # ── Disk rendering ─────────────────────────
    def _render_disk(self):
        c = self.disk_canvas
        c.delete("all")
        w = c.winfo_width() or 900
        cols = 64
        rows = SECTOR_COUNT // cols
        cell_w = w / cols
        cell_h = 100 / rows
        for i, status in enumerate(self.disk.sectors):
            row, col = divmod(i, cols)
            x1 = col * cell_w + 1
            y1 = row * cell_h + 1
            x2 = x1 + cell_w - 2
            y2 = y1 + cell_h - 2
            color = STATUS_COLORS[status]
            c.create_rectangle(x1, y1, x2, y2, fill=color, outline="")

        used  = sum(1 for s in self.disk.sectors if s == STATUS_USED)
        corr  = sum(1 for s in self.disk.sectors if s == STATUS_CORRUPTED)
        recov = sum(1 for s in self.disk.sectors if s == STATUS_RECOVERED)
        bad   = sum(1 for s in self.disk.sectors if s == STATUS_BAD)
        total_used = used + corr + recov + bad
        pct   = round(total_used / SECTOR_COUNT * 100)
        cpct  = round(corr / SECTOR_COUNT * 100)

        self.lbl_total["text"]   = str(SECTOR_COUNT)
        self.lbl_used["text"]    = str(total_used)
        self.lbl_free["text"]    = str(SECTOR_COUNT - total_used)
        self.lbl_corrupt["text"] = str(corr)
        self.usage_pb["value"]   = pct
        self.usage_pct["text"]   = f"{pct}%"
        self.corrupt_pb["value"] = cpct
        self.corrupt_pct["text"] = f"{cpct}%"
        self._update_recovery_stats()

    def _update_recovery_stats(self):
        fc = sum(1 for f in self.disk.files if f["status"]=="corrupt")
        fr = sum(1 for f in self.disk.files if f["status"]=="recovered")
        fl = sum(1 for f in self.disk.files if f["status"]=="lost")
        self.lbl_r_corrupt["text"]   = str(fc)
        self.lbl_r_recovered["text"] = str(fr)
        self.lbl_r_lost["text"]      = str(fl)

    def _refresh_file_tree(self):
        self.file_tree.delete(*self.file_tree.get_children())
        tag_colors = {"ok": COLORS["green"], "corrupt": COLORS["red"],
                      "recovered": COLORS["blue"], "lost": COLORS["amber"]}
        for f in self.disk.files:
            sec_range = f"{f['sectors'][0]}-{f['sectors'][-1]}" if f['sectors'] else "-"
            tag = f["status"]
            self.file_tree.insert("", tk.END, values=(
                f["name"], f["ftype"].upper(), f"{f['size_kb']}KB",
                sec_range, f["status"].upper(), f["checksum"]
            ), tags=(tag,))
        for t, c in tag_colors.items():
            self.file_tree.tag_configure(t, foreground=c)

    # ── Module 1 actions ─────────────────────
    def _write_file(self):
        name  = self.fname_var.get().strip() or f"file_{len(self.disk.files)}"
        ftype = self.ftype_var.get()
        entry, err = self.disk.write_file(name, ftype)
        if err:
            self._log(self.log1, err, "err")
            return
        sec_range = f"{entry['sectors'][0]}-{entry['sectors'][-1]}"
        self._log(self.log1,
                  f"WRITE {name}.{ftype} ({entry['size_kb']}KB) → sectors {sec_range}", "ok")
        self._log(self.log2,
                  f"JOURNAL: WRITE {name}.{ftype} checksum={entry['checksum']}", "info")
        self.btree.insert(name, entry)
        self.lru.put(f"{name}.{ftype}", entry)
        self._render_disk()
        self._refresh_file_tree()

    def _crash(self, mode):
        events = self.disk.simulate_crash(mode)
        for e in events:
            self._log(self.log1, f"CRASH [{mode.upper()}]: {e}", "err")
            self._log(self.log2, f"JOURNAL: CRASH EVENT — {e}", "err")
        self.status_dot["fg"] = COLORS["red"]
        self.status_lbl["text"] = "ALERT: Disk crash detected — run recovery engine"
        self._render_disk()
        self._refresh_file_tree()

    def _reset_disk(self):
        self.disk.reset()
        self.btree = BTree()
        self.lru   = LRUCache(capacity=4)
        self.bench_results = []
        self.status_dot["fg"] = COLORS["green"]
        self.status_lbl["text"] = "System nominal — disk mounted"
        self._log(self.log1, "Disk reset — all sectors cleared", "warn")
        self._render_disk()
        self._refresh_file_tree()
        self.chart_canvas.delete("all")
        self.btree_canvas.delete("all")
        self.lru_canvas.delete("all")

    # ── Module 2 actions ─────────────────────
    def _scan_signatures(self):
        corrupt = [f for f in self.disk.files if f["status"]=="corrupt"]
        if not corrupt:
            self._log(self.log2, "No corrupted files — simulate a crash first", "warn")
            return
        self._log(self.log2, "Starting file signature scan...", "info")
        results = self.disk.scan_signatures()
        for f, sig, sector in results:
            self._log(self.log2,
                      f"FOUND signature {sig} at sector {sector} → {f['name']}.{f['ftype']}", "ok")
        messagebox.showinfo("Scan Complete",
                            f"Found {len(results)} recoverable file signatures")

    def _recover_journal(self):
        def run():
            self.recovery_lbl["text"] = "Replaying journal entries..."
            for i in range(0, 80, 10):
                self.recovery_pb["value"] = i
                time.sleep(0.15)
            recovered, failed = self.disk.recover_journal()
            self.recovery_pb["value"] = 100
            for f in recovered:
                self._log(self.log2,
                          f"RESTORED {f['name']}.{f['ftype']} via journal (checksum: {f['checksum']})", "ok")
            for f in failed:
                self._log(self.log2,
                          f"JOURNAL MISS: {f['name']}.{f['ftype']} — try signature scan", "warn")
            self.recovery_lbl["text"] = f"Journal recovery: {len(recovered)} restored, {len(failed)} failed"
            self._render_disk()
            self._refresh_file_tree()
        threading.Thread(target=run, daemon=True).start()

    def _recover_all(self):
        def run():
            steps = ["Scanning inodes...", "Rebuilding FAT...",
                     "Applying journal...", "Signature matching...", "Writing data..."]
            for i, step in enumerate(steps):
                self.recovery_lbl["text"] = step
                self.recovery_pb["value"] = (i+1)*20
                time.sleep(0.5)
            recovered, lost = self.disk.recover_all()
            for f in recovered:
                self._log(self.log2, f"RECOVERED: {f['name']}.{f['ftype']}", "ok")
            for f in lost:
                self._log(self.log2, f"UNRECOVERABLE: {f['name']}.{f['ftype']}", "err")
            self.status_dot["fg"] = COLORS["green"]
            self.status_lbl["text"] = f"Recovery complete — {len(recovered)} restored, {len(lost)} lost"
            self.recovery_lbl["text"] = f"Done: {len(recovered)} recovered, {len(lost)} unrecoverable"
            self._render_disk()
            self._refresh_file_tree()
        threading.Thread(target=run, daemon=True).start()

    # ── Module 3 actions ─────────────────────
    def _benchmark(self, mode):
        def run():
            read_spd, write_spd = self.disk.benchmark(mode)
            self.bench_results.append((mode, read_spd, write_spd))
            self.lbl_read["text"]  = f"{read_spd} MB/s"
            self.lbl_write["text"] = f"{write_spd} MB/s"
            base_read = self.bench_results[0][1] if self.bench_results else read_spd
            speedup = round(read_spd / max(base_read, 1), 1)
            self.lbl_speedup["text"] = f"{speedup}×"
            labels = {"none":"No Opt","btree":"B-Tree","lru":"LRU","both":"Full Opt"}
            self._log(self.log3,
                      f"[{labels[mode]}] Read={read_spd} MB/s  Write={write_spd} MB/s  Speedup={speedup}×",
                      "ok" if mode != "none" else "warn")
            self._draw_benchmark_chart()
            if mode in ("btree","both"):
                self._draw_btree()
            if mode in ("lru","both"):
                self._draw_lru()
            if mode == "both":
                n = self.disk.defragment()
                self._log(self.log3, f"Defragmentation complete — {n} files compacted", "ok")
                self._render_disk()
        threading.Thread(target=run, daemon=True).start()

    def _draw_benchmark_chart(self):
        c = self.chart_canvas
        c.delete("all")
        w = c.winfo_width() or 700
        h = 170
        margin = 40
        bar_colors = {"none":COLORS["red"],"btree":COLORS["blue"],
                      "lru":COLORS["blue"],"both":COLORS["green"]}
        labels = {"none":"No Opt","btree":"B-Tree","lru":"LRU","both":"Full"}
        max_val = max((r[1] for r in self.bench_results), default=100) * 1.2
        n = len(self.bench_results)
        if n == 0:
            return
        bar_w = (w - 2*margin) / (n*2)
        for i, (mode, read, write) in enumerate(self.bench_results):
            x = margin + i * (w - 2*margin) / n
            rh = (read/max_val) * (h - margin - 10)
            wh = (write/max_val) * (h - margin - 10)
            # read bar
            c.create_rectangle(x+4, h-margin-rh, x+bar_w, h-margin,
                               fill=bar_colors.get(mode, COLORS["blue"]), outline="")
            c.create_text(x+bar_w//2+4, h-margin-rh-8,
                         text=f"{read:.0f}", fill=COLORS["text"], font=("Courier",8))
            # write bar
            c.create_rectangle(x+bar_w+8, h-margin-wh, x+2*bar_w+4, h-margin,
                               fill=COLORS["amber"], outline="")
            c.create_text(x+bar_w*1.5+6, h-margin-wh-8,
                         text=f"{write:.0f}", fill=COLORS["text"], font=("Courier",8))
            # label
            c.create_text(x+bar_w, h-margin+12,
                         text=labels.get(mode, mode), fill=COLORS["muted"], font=("Courier",8))
        # axis
        c.create_line(margin, 10, margin, h-margin, fill=COLORS["muted"])
        c.create_line(margin, h-margin, w-margin, h-margin, fill=COLORS["muted"])
        c.create_text(5, 30, text="MB/s", fill=COLORS["muted"], font=("Courier",8), angle=90)
        # legend
        c.create_rectangle(w-120, 10, w-110, 20, fill=COLORS["blue"], outline="")
        c.create_text(w-100, 15, text="Read", fill=COLORS["muted"], font=("Courier",8), anchor="w")
        c.create_rectangle(w-120, 25, w-110, 35, fill=COLORS["amber"], outline="")
        c.create_text(w-100, 30, text="Write", fill=COLORS["muted"], font=("Courier",8), anchor="w")

    def _draw_btree(self):
        c = self.btree_canvas
        c.delete("all")
        keys = self.btree.traverse()
        if not keys:
            c.create_text(150, 50, text="B-Tree empty — write files first",
                         fill=COLORS["muted"], font=("Courier",9))
            return
        w = c.winfo_width() or 400
        # Root node
        mid = keys[len(keys)//2]
        self._draw_node(c, w//2, 20, [mid], COLORS["accent"])
        # Children
        left_keys  = keys[:len(keys)//2]
        right_keys = keys[len(keys)//2+1:]
        if left_keys:
            self._draw_node(c, w//4, 65, left_keys[:2], COLORS["blue"])
            c.create_line(w//2, 35, w//4+30, 62, fill=COLORS["muted"])
        if right_keys:
            self._draw_node(c, 3*w//4, 65, right_keys[:2], COLORS["blue"])
            c.create_line(w//2, 35, 3*w//4-30, 62, fill=COLORS["muted"])
        c.create_text(w//2, 95,
                     text=f"O(log n) lookup · {len(keys)} keys · depth 2",
                     fill=COLORS["muted"], font=("Courier",8))

    def _draw_node(self, canvas, x, y, keys, color):
        label = " | ".join(str(k)[:6] for k in keys)
        canvas.create_rectangle(x-40, y, x+40, y+22, fill=color, outline="")
        canvas.create_text(x, y+11, text=label, fill="white", font=("Courier",8))

    def _draw_lru(self):
        c = self.lru_canvas
        c.delete("all")
        snapshot = self.lru.snapshot()
        w = c.winfo_width() or 400
        slot_w = (w - 20) // 4
        labels_top = ["MRU", "slot 2", "slot 3", "LRU"]
        for i in range(4):
            x = 10 + i * slot_w
            color = COLORS["accent"] if i == 0 else COLORS["surface"]
            c.create_rectangle(x, 15, x+slot_w-4, 75,
                               fill=color, outline=COLORS["border"])
            top_lbl = labels_top[i]
            c.create_text(x+slot_w//2-2, 25, text=top_lbl,
                         fill=COLORS["muted"], font=("Courier",7))
            if i < len(snapshot):
                name, _ = snapshot[i]
                c.create_text(x+slot_w//2-2, 48, text=name[:8],
                             fill=COLORS["text"], font=("Courier",9,"bold"))
            else:
                c.create_text(x+slot_w//2-2, 48, text="(empty)",
                             fill=COLORS["muted"], font=("Courier",8))
        c.create_text(w//2, 88, text="← Most Recent Used                Least Recent Used →",
                     fill=COLORS["muted"], font=("Courier",7))


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
