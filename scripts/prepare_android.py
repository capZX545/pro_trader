"""Stage the desktop engine for the Android build (Chaquopy packages Python source dirs verbatim).

    python scripts/prepare_android.py        →  ./pysrc/{core,strategies,web,ptdata,RELEASE_NOTES.md}

Nothing is rewritten: core/ and strategies/ are byte-identical copies of the desktop modules; web/ is the mobile UI
already served by core/webapp.py; ptdata/ carries the trained seeds (playbook, validation, audit, vision/ML models)
so the phone starts with the same knowledge as the PC. Parquet market caches are NOT shipped (downloaded on demand).
"""
import os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "pysrc")
SKIP_DIRS = {"__pycache__", ".pytest_cache"}
SEED_FILES = ("playbook.json", "validation.json", "audit.json", "vision_real.json", "vision_robustness.json")


def copytree(src, dst):
    for r, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        rel = os.path.relpath(r, src)
        od = os.path.join(dst, rel) if rel != "." else dst
        os.makedirs(od, exist_ok=True)
        for f in files:
            if f.endswith((".pyc", ".pyo")):
                continue
            shutil.copy2(os.path.join(r, f), os.path.join(od, f))


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    for pkg in ("core", "strategies", "web"):
        copytree(os.path.join(ROOT, pkg), os.path.join(OUT, pkg))
    for pkg in ("web",):                                   # make it importable-as-package so Chaquopy extracts it lazily
        init = os.path.join(OUT, pkg, "__init__.py")
        if not os.path.exists(init):
            open(init, "w").close()
    seed = os.path.join(OUT, "ptdata"); os.makedirs(seed)
    open(os.path.join(seed, "__init__.py"), "w").close()
    data = os.path.join(ROOT, "data")
    for f in SEED_FILES:
        p = os.path.join(data, f)
        if os.path.exists(p):
            shutil.copy2(p, seed)
    models = os.path.join(data, "models")
    if os.path.isdir(models):
        shutil.copytree(models, os.path.join(seed, "models"), ignore=shutil.ignore_patterns("*.bin", "__pycache__"))
    shutil.copy2(os.path.join(ROOT, "RELEASE_NOTES.md"), OUT)
    n = sum(len(f) for _, _, f in os.walk(OUT)); mb = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(OUT) for f in fs) / 1e6
    print(f"staged {n} files, {mb:.1f} MB → {OUT}")
    # sanity: the engine must import with nothing but the staged tree on sys.path
    sys.path.insert(0, OUT); os.environ["PROTRADER_DATA"] = os.path.join(OUT, "_selftest"); os.environ["PROTRADER_NO_MAINT"] = "1"
    import core.webapp, strategies  # noqa
    assert len(strategies.REGISTRY) >= 179, len(strategies.REGISTRY)
    print("engine imports OK:", len(strategies.REGISTRY), "strategies, version", core.webapp._version())
    shutil.rmtree(os.environ["PROTRADER_DATA"], ignore_errors=True)


if __name__ == "__main__":
    main()
