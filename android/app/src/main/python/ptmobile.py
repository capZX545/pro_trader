"""Android entry point (Chaquopy). Runs the SAME ProTrader engine as the desktop — core/, strategies/, web/ verbatim —
as a local HTTP server on 127.0.0.1 and the Java side shows web/index.html in a WebView.
Writable data (cache, playbook, journal, drawings, models) lives in $HOME/protrader (app-private storage)."""
import os, sys, shutil, threading, time


def _seed(dst):
    """first run: copy bundled seed data (playbook, validation, audit, models) into the writable dir"""
    try:
        import ptdata
        src = os.path.dirname(ptdata.__file__)
    except Exception:
        return
    for name in os.listdir(src):
        if name.startswith("__"):
            continue
        s, d = os.path.join(src, name), os.path.join(dst, name)
        if os.path.exists(d):
            continue
        try:
            (shutil.copytree if os.path.isdir(s) else shutil.copy2)(s, d)
        except Exception:
            pass


def _find_web(root_hint):
    try:
        import web                                          # Chaquopy extracts a package's data files on first import
        return os.path.dirname(web.__file__)
    except Exception:
        pass
    for base in [root_hint] + sys.path:
        p = os.path.join(base, "web", "index.html")
        if os.path.isfile(p):
            return os.path.dirname(p)
    return None


_port = [0]


def start(port=8765):
    """idempotent; returns the bound port"""
    if _port[0]:
        return _port[0]
    home = os.environ.get("HOME") or "/data/local/tmp"
    data = os.path.join(home, "protrader")
    os.makedirs(data, exist_ok=True)
    os.environ.setdefault("PROTRADER_DATA", data)
    os.environ.setdefault("PROTRADER_NO_MAINT", "0")       # background self-training/forward-test like the desktop
    os.environ.setdefault("MPLCONFIGDIR", os.path.join(home, "mpl"))
    _seed(data)
    from core import webapp
    web = _find_web(webapp.ROOT)
    if web:
        webapp.WEB_DIR = web
    url, p = webapp.start(port=port, host="127.0.0.1")
    _port[0] = p
    try:                                                   # same maintenance loop as the desktop (forward test, health autofix, playbook)
        from core import maintenance
        if os.environ.get("PROTRADER_NO_MAINT") != "1":
            maintenance.start()
    except Exception:
        pass
    return p


def port():
    return _port[0]


def version():
    try:
        from core import webapp
        return webapp._version()
    except Exception:
        return "dev"
