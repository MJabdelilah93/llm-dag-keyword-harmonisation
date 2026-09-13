"""M7 local annotation GUI (Tkinter). A packaging/UX layer only -- it does
not change the frozen scientific annotation protocol. Business logic
(session state, autosave, resume, audit log) lives in session.py, kept
separate from the Tkinter view (app.py) so it can be unit-tested without
a display.
"""
