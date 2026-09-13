"""Tkinter view layer for the M7 H3 retrieval-audit GUI. Thin -- all state
lives in retrieval_session.RetrievalAnnotationSession. Mirrors app.py's
structure (same one-pair-per-screen layout, same buttons/shortcuts) but
shows seed_string/candidate_string rather than string_a/string_b, and
never exposes retrieval score/route/rank/pool-membership metadata (the
pristine retrieval workbooks never carry those columns in the first
place, so there is nothing here that could leak them).
"""
from __future__ import annotations

import textwrap
import tkinter as tk
from tkinter import ttk

from .context_lookup import CombinedContextLookup
from .retrieval_session import ALLOWED_LABELS, RetrievalAnnotationSession

DOMAIN_LABELS = {"circular_economy": "Circular Economy", "biomedical_diabetes_mellitus": "Diabetes Mellitus"}

BG = "#FAFAFA"
FG = "#222222"
MUTED = "#888888"
BTN_MATCH = "#DCE8FF"
BTN_NONMATCH = "#FFE8DC"
BTN_UNCERTAIN = "#F3E8FF"
BTN_NEUTRAL = "#EFEFEF"


class RetrievalApp:
    def __init__(self, session: RetrievalAnnotationSession, context: CombinedContextLookup, annotator_label: str):
        self.session = session
        self.context = context
        self.annotator_label = annotator_label

        self.root = tk.Tk()
        self.root.title(f"M7 Retrieval Audit - {annotator_label}")
        self.root.geometry("1100x700")
        self.root.minsize(1024, 700)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_home_screen()

    def run(self):
        self.root.mainloop()

    # -- HOME / STATUS SCREEN --------------------------------------------
    def _build_home_screen(self):
        for w in self.root.winfo_children():
            w.destroy()
        completed, total = self.session.progress()
        frame = tk.Frame(self.root, bg=BG)
        frame.pack(expand=True, fill="both")

        tk.Label(frame, text="M7 Retrieval Audit", font=("Segoe UI", 26, "bold"), bg=BG, fg=FG).pack(pady=(50, 10))
        tk.Label(frame, text=self.annotator_label, font=("Segoe UI", 16), bg=BG, fg=FG).pack()
        tk.Label(frame, text=f"Completed: {completed} / {total}", font=("Segoe UI", 14), bg=BG, fg=FG).pack(pady=(20, 2))
        tk.Label(frame, text=f"Remaining: {total - completed}", font=("Segoe UI", 14), bg=BG, fg=MUTED).pack()
        if completed < total:
            current_domain = DOMAIN_LABELS.get(self.session.current_pair().domain, "")
            tk.Label(frame, text=f"Current domain: {current_domain}", font=("Segoe UI", 12), bg=BG, fg=MUTED).pack(pady=(2, 0))

        tk.Label(
            frame, text="You can close this window and resume later; progress is saved.",
            font=("Segoe UI", 10, "italic"), bg=BG, fg=MUTED,
        ).pack(pady=(16, 0))

        btn_frame = tk.Frame(frame, bg=BG)
        btn_frame.pack(pady=40)
        tk.Button(
            btn_frame, text="CONTINUE ANNOTATION", font=("Segoe UI", 14, "bold"), bg=BTN_MATCH,
            width=24, height=2, command=self._build_annotation_screen,
        ).pack(side="left", padx=10)
        tk.Button(
            btn_frame, text="REVIEW COMPLETED", font=("Segoe UI", 12), bg=BTN_NEUTRAL,
            width=20, height=2, command=self._build_review_screen,
        ).pack(side="left", padx=10)

    # -- MAIN ANNOTATION SCREEN -------------------------------------------
    def _build_annotation_screen(self):
        for w in self.root.winfo_children():
            w.destroy()

        if self.session.is_complete():
            self._build_complete_screen()
            return

        pair = self.session.current_pair()
        completed, total = self.session.progress()
        pct = round(100 * completed / total, 1) if total else 0.0

        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=16, pady=(10, 0))
        tk.Label(top, text="M7 Retrieval Audit", font=("Segoe UI", 12, "bold"), bg=BG, fg=FG).pack(side="left")
        tk.Label(top, text=f"  |  {self.annotator_label}", font=("Segoe UI", 12), bg=BG, fg=FG).pack(side="left")
        tk.Label(top, text=f"  |  {DOMAIN_LABELS.get(pair.domain, pair.domain)}", font=("Segoe UI", 12), bg=BG, fg=MUTED).pack(side="left")
        tk.Label(top, text=f"Row {self.session.current_index + 1} of {total}", font=("Segoe UI", 12), bg=BG, fg=FG).pack(side="right")

        status = tk.Frame(self.root, bg=BG)
        status.pack(fill="x", padx=16, pady=(0, 6))
        tk.Label(status, text=f"Completed {completed} / {total}  ({pct}%)", font=("Segoe UI", 11), bg=BG, fg=MUTED).pack(side="left")
        pbar = ttk.Progressbar(status, orient="horizontal", length=300, mode="determinate", maximum=total, value=completed)
        pbar.pack(side="right")

        center = tk.Frame(self.root, bg=BG)
        center.pack(expand=True, fill="both", padx=40, pady=10)

        tk.Label(center, text="SEED KEYWORD", font=("Segoe UI", 13, "bold"), bg=BG, fg=MUTED).pack(pady=(10, 0))
        a_text = "\n".join(textwrap.wrap(pair.seed_string, width=60)) or pair.seed_string
        tk.Label(center, text=a_text, font=("Segoe UI", 26), bg=BG, fg=FG, wraplength=900, justify="center").pack(pady=(0, 10))

        tk.Label(center, text="versus", font=("Segoe UI", 13, "italic"), bg=BG, fg=MUTED).pack()

        tk.Label(center, text="CANDIDATE KEYWORD", font=("Segoe UI", 13, "bold"), bg=BG, fg=MUTED).pack(pady=(10, 0))
        b_text = "\n".join(textwrap.wrap(pair.candidate_string, width=60)) or pair.candidate_string
        tk.Label(center, text=b_text, font=("Segoe UI", 26), bg=BG, fg=FG, wraplength=900, justify="center").pack(pady=(0, 10))

        tk.Label(center, text=f"retrieval_pair_id: {pair.retrieval_pair_id}", font=("Segoe UI", 8), bg=BG, fg="#BBBBBB").pack(side="bottom", anchor="w")

        decision_frame = tk.Frame(self.root, bg=BG)
        decision_frame.pack(pady=(0, 10))
        tk.Button(decision_frame, text="MATCH\n(1 / M)", font=("Segoe UI", 15, "bold"), bg=BTN_MATCH, width=16, height=3,
                  command=lambda: self._decide("match")).pack(side="left", padx=12)
        tk.Button(decision_frame, text="NON-MATCH\n(2 / N)", font=("Segoe UI", 15, "bold"), bg=BTN_NONMATCH, width=16, height=3,
                  command=lambda: self._decide("non-match")).pack(side="left", padx=12)
        tk.Button(decision_frame, text="UNCERTAIN\n(3 / U)", font=("Segoe UI", 15, "bold"), bg=BTN_UNCERTAIN, width=16, height=3,
                  command=lambda: self._decide("uncertain")).pack(side="left", padx=12)

        aux_frame = tk.Frame(self.root, bg=BG)
        aux_frame.pack(pady=(0, 6))
        tk.Button(aux_frame, text="MORE CONTEXT (C)", bg=BTN_NEUTRAL, command=self._open_context).pack(side="left", padx=6)
        tk.Button(aux_frame, text="ADD NOTE (J)", bg=BTN_NEUTRAL, command=self._open_justification).pack(side="left", padx=6)
        tk.Button(aux_frame, text="BACK (← / B)", bg=BTN_NEUTRAL, command=self._back).pack(side="left", padx=6)
        tk.Button(aux_frame, text="SKIP FOR NOW (S)", bg=BTN_NEUTRAL, command=self._skip).pack(side="left", padx=6)
        tk.Button(aux_frame, text="NEXT UNRESOLVED (→)", bg=BTN_NEUTRAL, command=self._next_unresolved).pack(side="left", padx=6)

        tk.Label(
            self.root, bg=BG, fg=MUTED, font=("Segoe UI", 9),
            text="Shortcuts: 1/M=Match  2/N=Non-match  3/U=Uncertain  C=Context  J=Note  ←/B=Back  →=Next unresolved  S=Skip",
        ).pack(side="bottom", pady=(0, 8))

        self._bind_shortcuts()

    def _bind_shortcuts(self):
        r = self.root
        for key in ("1", "m", "M"):
            r.bind(key, lambda e: self._decide("match"))
        for key in ("2", "n", "N"):
            r.bind(key, lambda e: self._decide("non-match"))
        for key in ("3", "u", "U"):
            r.bind(key, lambda e: self._decide("uncertain"))
        for key in ("c", "C"):
            r.bind(key, lambda e: self._open_context())
        for key in ("j", "J"):
            r.bind(key, lambda e: self._open_justification())
        for key in ("b", "B", "<Left>"):
            r.bind(key, lambda e: self._back())
        r.bind("<Right>", lambda e: self._next_unresolved())
        for key in ("s", "S"):
            r.bind(key, lambda e: self._skip())

    def _decide(self, label: str):
        assert label in ALLOWED_LABELS
        self.session.decide(label)
        self._build_annotation_screen()

    def _skip(self):
        self.session.skip()
        self._build_annotation_screen()

    def _back(self):
        self.session.go_back()
        self._build_annotation_screen()

    def _next_unresolved(self):
        self.session.go_next_unresolved()
        self._build_annotation_screen()

    def _open_context(self):
        self.session.mark_context_opened()
        pair = self.session.current_pair()
        popup = tk.Toplevel(self.root)
        popup.title("More Context")
        popup.configure(bg=BG)
        popup.geometry("600x420")
        popup.bind("<Escape>", lambda e: popup.destroy())
        popup.grab_set()

        for label, string in (("Seed keyword", pair.seed_string), ("Candidate keyword", pair.candidate_string)):
            tk.Label(popup, text=label, font=("Segoe UI", 13, "bold"), bg=BG, fg=FG).pack(anchor="w", padx=16, pady=(12, 0))
            tk.Label(popup, text=string, font=("Segoe UI", 11, "italic"), bg=BG, fg=MUTED, wraplength=560, justify="left").pack(anchor="w", padx=16)
            titles = self.context.titles_for(string)
            if titles:
                for t in titles:
                    tk.Label(popup, text=f"• {t}", font=("Segoe UI", 10), bg=BG, fg=FG, wraplength=560, justify="left").pack(anchor="w", padx=32, pady=1)
            else:
                tk.Label(popup, text="(no titles available)", font=("Segoe UI", 10, "italic"), bg=BG, fg=MUTED).pack(anchor="w", padx=32)

        tk.Button(popup, text="Close", command=popup.destroy, bg=BTN_NEUTRAL).pack(pady=16)
        popup.wait_window()
        self._build_annotation_screen()

    def _open_justification(self):
        pair = self.session.current_pair()
        popup = tk.Toplevel(self.root)
        popup.title("Note")
        popup.configure(bg=BG)
        popup.geometry("500x260")
        popup.bind("<Escape>", lambda e: popup.destroy())
        popup.grab_set()

        tk.Label(popup, text="Note (optional)", font=("Segoe UI", 12, "bold"), bg=BG, fg=FG).pack(anchor="w", padx=16, pady=(12, 4))
        text = tk.Text(popup, width=55, height=8, wrap="word")
        text.insert("1.0", pair.justification or "")
        text.pack(padx=16)

        def save_and_close():
            self.session.set_justification(text.get("1.0", "end").strip())
            popup.destroy()

        tk.Button(popup, text="Save", command=save_and_close, bg=BTN_MATCH).pack(pady=12)
        popup.wait_window()

    # -- COMPLETE SCREEN ---------------------------------------------------
    def _build_complete_screen(self):
        for w in self.root.winfo_children():
            w.destroy()
        completed_path = self.session.write_completed_if_done()
        frame = tk.Frame(self.root, bg=BG)
        frame.pack(expand=True, fill="both")
        tk.Label(frame, text="RETRIEVAL AUDIT COMPLETE", font=("Segoe UI", 26, "bold"), bg=BG, fg="#1B7A2E").pack(pady=(120, 20))
        tk.Label(frame, text=f"All {len(self.session.pairs)} rows have a label.", font=("Segoe UI", 13), bg=BG, fg=FG).pack()
        if completed_path:
            tk.Label(frame, text=f"Completed file written:\n{completed_path.name}", font=("Segoe UI", 11), bg=BG, fg=MUTED).pack(pady=10)
        tk.Button(frame, text="REVIEW COMPLETED", bg=BTN_NEUTRAL, font=("Segoe UI", 12), command=self._build_review_screen).pack(pady=20)

    # -- REVIEW MODE ---------------------------------------------------
    def _build_review_screen(self):
        for w in self.root.winfo_children():
            w.destroy()

        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=16, pady=10)
        tk.Label(top, text="Review Completed / In-Progress Rows", font=("Segoe UI", 14, "bold"), bg=BG, fg=FG).pack(side="left")
        tk.Button(top, text="Back to annotation", bg=BTN_NEUTRAL, command=self._build_annotation_screen).pack(side="right")

        filter_frame = tk.Frame(self.root, bg=BG)
        filter_frame.pack(fill="x", padx=16)
        tk.Label(filter_frame, text="Filter:", bg=BG, fg=FG).pack(side="left")
        filter_var = tk.StringVar(value="all")
        options = ["all", "match", "non-match", "uncertain", "context_used", "unresolved"]
        combo = ttk.Combobox(filter_frame, textvariable=filter_var, values=options, state="readonly", width=16)
        combo.pack(side="left", padx=8)

        columns = ("retrieval_pair_id", "domain", "seed_string", "candidate_string", "label", "context_used")
        tree = ttk.Treeview(self.root, columns=columns, show="headings", height=20)
        for c in columns:
            tree.heading(c, text=c)
            tree.column(c, width=140 if c in ("seed_string", "candidate_string") else 100)
        tree.pack(expand=True, fill="both", padx=16, pady=10)

        def refresh(*_):
            tree.delete(*tree.get_children())
            f = filter_var.get()
            for p in self.session.pairs:
                if f == "match" and p.label != "match":
                    continue
                if f == "non-match" and p.label != "non-match":
                    continue
                if f == "uncertain" and p.label != "uncertain":
                    continue
                if f == "context_used" and p.context_used != "yes":
                    continue
                if f == "unresolved" and p.label:
                    continue
                tree.insert("", "end", iid=p.retrieval_pair_id, values=(p.retrieval_pair_id, DOMAIN_LABELS.get(p.domain, p.domain), p.seed_string, p.candidate_string, p.label, p.context_used))

        combo.bind("<<ComboboxSelected>>", refresh)
        refresh()

        def on_double_click(event):
            item = tree.selection()
            if item:
                self.session.jump_to(item[0])
                self._build_annotation_screen()

        tree.bind("<Double-1>", on_double_click)

    def _on_close(self):
        if any(p.label for p in self.session.pairs):
            self.session.backup_now()
        self.root.destroy()
