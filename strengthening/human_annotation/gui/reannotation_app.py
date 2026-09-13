"""Diabetes-only re-annotation GUI (diagnostic Steps 6-9). Reuses the
same one-pair Tkinter architecture and AnnotationSession as the primary
GUI (app.py/session.py), but prepends a refreshed-instructions screen and
a mandatory synthetic comprehension gate before the real 500-pair
re-annotation can begin. The session is initialised from a brand-new,
blank-label source file (DIABETES_REANNOTATION_ANNOTATOR_2.xlsx) that
contains no reference anywhere to the original Annotator 2 diabetes
labels, Annotator 1 labels, agreement status, or any model/system
information -- independence is structural, not merely a GUI filter.
"""
from __future__ import annotations

import textwrap
import tkinter as tk

from .app import App, BG, BTN_MATCH, BTN_NEUTRAL, BTN_NONMATCH, BTN_UNCERTAIN, FG, MUTED
from .comprehension_gate import COMPREHENSION_EXAMPLES, REFRESHED_INSTRUCTIONS_LINES, ComprehensionGateState
from .context_lookup import CombinedContextLookup
from .session import AnnotationSession


class ReannotationApp(App):
    def __init__(self, session: AnnotationSession, context: CombinedContextLookup, annotator_label: str):
        self._gate = ComprehensionGateState()
        # Intentionally does NOT call App.__init__ (which would jump straight
        # to the home screen) -- build the window ourselves and start with
        # the instructions screen instead.
        self.session = session
        self.context = context
        self.annotator_label = annotator_label

        self.root = tk.Tk()
        self.root.title(f"M7 Diabetes Re-annotation - {annotator_label}")
        self.root.geometry("1100x700")
        self.root.minsize(1024, 700)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_instructions_screen()

    # -- refreshed instructions -------------------------------------------
    def _build_instructions_screen(self):
        for w in self.root.winfo_children():
            w.destroy()
        frame = tk.Frame(self.root, bg=BG)
        frame.pack(expand=True, fill="both", padx=60, pady=40)
        for line in REFRESHED_INSTRUCTIONS_LINES:
            if line.startswith("#"):
                tk.Label(frame, text=line.lstrip("# "), font=("Segoe UI", 18, "bold"), bg=BG, fg=FG, wraplength=900, justify="left").pack(anchor="w", pady=(6, 10))
            elif line.strip() == "":
                continue
            elif line == "IMPORTANT REMINDER:":
                tk.Label(frame, text=line, font=("Segoe UI", 13, "bold"), bg=BG, fg="#B03A2E", wraplength=900, justify="left").pack(anchor="w", pady=(14, 2))
            else:
                tk.Label(frame, text=line, font=("Segoe UI", 12), bg=BG, fg=FG, wraplength=900, justify="left").pack(anchor="w", pady=2)
        tk.Button(
            frame, text="CONTINUE TO COMPREHENSION CHECK", font=("Segoe UI", 13, "bold"), bg=BTN_MATCH,
            command=self._build_comprehension_screen,
        ).pack(pady=30)

    # -- comprehension gate -------------------------------------------------
    def _build_comprehension_screen(self):
        for w in self.root.winfo_children():
            w.destroy()

        if self._gate.is_complete:
            self._build_annotation_screen()  # inherited from App -- the real 500-pair flow
            return

        example = self._gate.current_example()
        frame = tk.Frame(self.root, bg=BG)
        frame.pack(expand=True, fill="both", padx=40, pady=20)

        tk.Label(frame, text=f"Comprehension check {self._gate.current_index + 1} of {self._gate.total}",
                 font=("Segoe UI", 13, "bold"), bg=BG, fg=FG).pack(pady=(0, 10))
        tk.Label(frame, text="(These are training examples only -- not part of the benchmark.)",
                 font=("Segoe UI", 10, "italic"), bg=BG, fg=MUTED).pack(pady=(0, 20))

        tk.Label(frame, text="KEYWORD A", font=("Segoe UI", 12, "bold"), bg=BG, fg=MUTED).pack()
        tk.Label(frame, text=example.string_a, font=("Segoe UI", 20), bg=BG, fg=FG, wraplength=800).pack(pady=(0, 10))
        tk.Label(frame, text="versus", font=("Segoe UI", 12, "italic"), bg=BG, fg=MUTED).pack()
        tk.Label(frame, text="KEYWORD B", font=("Segoe UI", 12, "bold"), bg=BG, fg=MUTED).pack(pady=(10, 0))
        tk.Label(frame, text=example.string_b, font=("Segoe UI", 20), bg=BG, fg=FG, wraplength=800).pack(pady=(0, 20))

        self._feedback_label = tk.Label(frame, text="", font=("Segoe UI", 11), bg=BG, fg="#B03A2E", wraplength=900, justify="left")
        self._feedback_label.pack(pady=(0, 10))

        btns = tk.Frame(frame, bg=BG)
        btns.pack()
        tk.Button(btns, text="MATCH", font=("Segoe UI", 13, "bold"), bg=BTN_MATCH, width=14, height=2,
                  command=lambda: self._answer_comprehension("match")).pack(side="left", padx=10)
        tk.Button(btns, text="NON-MATCH", font=("Segoe UI", 13, "bold"), bg=BTN_NONMATCH, width=14, height=2,
                  command=lambda: self._answer_comprehension("non-match")).pack(side="left", padx=10)
        tk.Button(btns, text="UNCERTAIN", font=("Segoe UI", 13, "bold"), bg=BTN_UNCERTAIN, width=14, height=2,
                  command=lambda: self._answer_comprehension("uncertain")).pack(side="left", padx=10)

    def _answer_comprehension(self, label: str):
        correct = self._gate.answer(label)
        if correct:
            self._build_comprehension_screen()
        else:
            self._feedback_label.config(text=f"Not quite. {self._gate.last_explanation}\nPlease try this example again.")

    def _on_close(self):
        # Nothing to autosave during instructions/comprehension (no session
        # mutation has happened yet); once the real annotation screen is
        # reached, App's own _on_close (inherited) semantics apply via the
        # WM_DELETE_WINDOW binding set in App.__init__ -- but since we never
        # call App.__init__, re-bind explicitly once the real screen starts.
        if hasattr(self, "session") and any(p.label for p in getattr(self.session, "pairs", [])):
            self.session.backup_now()
        self.root.destroy()
