"""Tkinter view layer for the H2 primary adjudication GUI. Thin -- all
state lives in adjudication_session.AdjudicationSession. Shows Decision A
/ Decision B (already-anonymised annotator letters) but never which real
annotator made which decision, and never any stratum/score/frequency/
route/model-prediction metadata."""
from __future__ import annotations

import textwrap
import tkinter as tk

from strengthening.human_annotation.gui.context_lookup import CombinedContextLookup

from .adjudication_session import ALLOWED_LABELS, AdjudicationSession

DOMAIN_LABELS = {"circular_economy": "Circular Economy", "biomedical_diabetes_mellitus": "Diabetes Mellitus"}

BG = "#FAFAFA"
FG = "#222222"
MUTED = "#888888"
BTN_MATCH = "#DCE8FF"
BTN_NONMATCH = "#FFE8DC"
BTN_UNCERTAIN = "#F3E8FF"
BTN_NEUTRAL = "#EFEFEF"


class AdjudicationApp:
    def __init__(self, session: AdjudicationSession, context: CombinedContextLookup):
        self.session = session
        self.context = context

        self.root = tk.Tk()
        self.root.title("M7 Primary Adjudication")
        self.root.geometry("1100x700")
        self.root.minsize(1024, 700)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_screen()

    def run(self):
        self.root.mainloop()

    def _build_screen(self):
        for w in self.root.winfo_children():
            w.destroy()

        if self.session.is_complete():
            self._build_complete_screen()
            return

        row = self.session.current_row()
        completed, total = self.session.progress()
        pct = round(100 * completed / total, 1) if total else 0.0

        top = tk.Frame(self.root, bg=BG)
        top.pack(fill="x", padx=16, pady=(10, 0))
        tk.Label(top, text="M7 Primary Adjudication", font=("Segoe UI", 12, "bold"), bg=BG, fg=FG).pack(side="left")
        tk.Label(top, text=f"  |  {DOMAIN_LABELS.get(row.domain, row.domain)}", font=("Segoe UI", 12), bg=BG, fg=MUTED).pack(side="left")
        tk.Label(top, text=f"Disagreement {self.session.current_index + 1} of {total}", font=("Segoe UI", 12), bg=BG, fg=FG).pack(side="right")

        status = tk.Frame(self.root, bg=BG)
        status.pack(fill="x", padx=16, pady=(0, 6))
        tk.Label(status, text=f"Completed {completed} / {total}  ({pct}%)", font=("Segoe UI", 11), bg=BG, fg=MUTED).pack(side="left")
        from tkinter import ttk

        pbar = ttk.Progressbar(status, orient="horizontal", length=300, mode="determinate", maximum=total, value=completed)
        pbar.pack(side="right")

        center = tk.Frame(self.root, bg=BG)
        center.pack(expand=True, fill="both", padx=40, pady=6)

        tk.Label(center, text="KEYWORD A", font=("Segoe UI", 12, "bold"), bg=BG, fg=MUTED).pack(pady=(4, 0))
        a_text = "\n".join(textwrap.wrap(row.string_a, width=60)) or row.string_a
        tk.Label(center, text=a_text, font=("Segoe UI", 22), bg=BG, fg=FG, wraplength=900, justify="center").pack(pady=(0, 6))
        tk.Label(center, text="versus", font=("Segoe UI", 12, "italic"), bg=BG, fg=MUTED).pack()
        tk.Label(center, text="KEYWORD B", font=("Segoe UI", 12, "bold"), bg=BG, fg=MUTED).pack(pady=(6, 0))
        b_text = "\n".join(textwrap.wrap(row.string_b, width=60)) or row.string_b
        tk.Label(center, text=b_text, font=("Segoe UI", 22), bg=BG, fg=FG, wraplength=900, justify="center").pack(pady=(0, 6))

        decisions = tk.Frame(center, bg=BG)
        decisions.pack(pady=(6, 0))
        tk.Label(decisions, text=f"Decision A: {row.decision_A}", font=("Segoe UI", 13, "bold"), bg=BG, fg=FG).pack(side="left", padx=20)
        tk.Label(decisions, text=f"Decision B: {row.decision_B}", font=("Segoe UI", 13, "bold"), bg=BG, fg=FG).pack(side="left", padx=20)

        tk.Button(center, text="VIEW ANNOTATOR NOTES", bg=BTN_NEUTRAL, command=self._view_notes).pack(pady=(8, 0))
        tk.Label(center, text=f"pair_id: {row.pair_id}", font=("Segoe UI", 8), bg=BG, fg="#BBBBBB").pack(side="bottom", anchor="w")

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
        tk.Button(aux_frame, text="ADD NOTE", bg=BTN_NEUTRAL, command=self._open_note).pack(side="left", padx=6)
        tk.Button(aux_frame, text="BACK (← / B)", bg=BTN_NEUTRAL, command=self._back).pack(side="left", padx=6)
        tk.Button(aux_frame, text="SKIP FOR NOW (S)", bg=BTN_NEUTRAL, command=self._skip).pack(side="left", padx=6)

        tk.Label(
            self.root, bg=BG, fg=MUTED, font=("Segoe UI", 9),
            text="Shortcuts: 1/M=Match  2/N=Non-match  3/U=Uncertain  C=Context  ←/B=Back  S=Skip",
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
        for key in ("b", "B", "<Left>"):
            r.bind(key, lambda e: self._back())
        for key in ("s", "S"):
            r.bind(key, lambda e: self._skip())

    def _decide(self, label: str):
        assert label in ALLOWED_LABELS
        self.session.decide(label)
        self._build_screen()

    def _skip(self):
        self.session.skip()
        self._build_screen()

    def _back(self):
        self.session.go_back()
        self._build_screen()

    def _open_context(self):
        self.session.mark_context_opened()
        row = self.session.current_row()
        popup = tk.Toplevel(self.root)
        popup.title("More Context")
        popup.configure(bg=BG)
        popup.geometry("600x420")
        popup.bind("<Escape>", lambda e: popup.destroy())
        popup.grab_set()
        for label, string in (("Keyword A", row.string_a), ("Keyword B", row.string_b)):
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
        self._build_screen()

    def _open_note(self):
        row = self.session.current_row()
        popup = tk.Toplevel(self.root)
        popup.title("Adjudicator Note")
        popup.configure(bg=BG)
        popup.geometry("500x260")
        popup.bind("<Escape>", lambda e: popup.destroy())
        popup.grab_set()
        tk.Label(popup, text="Adjudicator note (optional)", font=("Segoe UI", 12, "bold"), bg=BG, fg=FG).pack(anchor="w", padx=16, pady=(12, 4))
        text = tk.Text(popup, width=55, height=8, wrap="word")
        text.insert("1.0", row.adjudicator_notes or "")
        text.pack(padx=16)

        def save_and_close():
            self.session.set_notes(text.get("1.0", "end").strip())
            popup.destroy()

        tk.Button(popup, text="Save", command=save_and_close, bg=BTN_MATCH).pack(pady=12)
        popup.wait_window()

    def _view_notes(self):
        row = self.session.current_row()
        popup = tk.Toplevel(self.root)
        popup.title("Annotator Notes (Justifications)")
        popup.configure(bg=BG)
        popup.geometry("560x320")
        popup.bind("<Escape>", lambda e: popup.destroy())
        popup.grab_set()
        tk.Label(popup, text="Annotator A justification:", font=("Segoe UI", 11, "bold"), bg=BG, fg=FG).pack(anchor="w", padx=16, pady=(12, 0))
        tk.Label(popup, text=row.justification_A or "(none provided)", font=("Segoe UI", 10), bg=BG, fg=FG, wraplength=520, justify="left").pack(anchor="w", padx=16)
        tk.Label(popup, text="Annotator B justification:", font=("Segoe UI", 11, "bold"), bg=BG, fg=FG).pack(anchor="w", padx=16, pady=(16, 0))
        tk.Label(popup, text=row.justification_B or "(none provided)", font=("Segoe UI", 10), bg=BG, fg=FG, wraplength=520, justify="left").pack(anchor="w", padx=16)
        tk.Button(popup, text="Close", command=popup.destroy, bg=BTN_NEUTRAL).pack(pady=16)
        popup.wait_window()

    def _build_complete_screen(self):
        for w in self.root.winfo_children():
            w.destroy()
        completed_path = self.session.write_completed_if_done()
        frame = tk.Frame(self.root, bg=BG)
        frame.pack(expand=True, fill="both")
        tk.Label(frame, text="ADJUDICATION COMPLETE", font=("Segoe UI", 26, "bold"), bg=BG, fg="#1B7A2E").pack(pady=(140, 20))
        tk.Label(frame, text=f"All {len(self.session.rows)} disagreements have an adjudicated label.", font=("Segoe UI", 13), bg=BG, fg=FG).pack()
        if completed_path:
            tk.Label(frame, text=f"Completed file written:\n{completed_path.name}", font=("Segoe UI", 11), bg=BG, fg=MUTED).pack(pady=10)

    def _on_close(self):
        if any(r.adjudicated_label for r in self.session.rows):
            self.session.backup_now()
        self.root.destroy()
