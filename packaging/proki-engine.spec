# The launcher and the engine as one program, a folder of it, for the app to ship.
#
#     uv run pyinstaller packaging/proki-engine.spec --distpath build/engine --workpath build/pyinstaller
#
# packaging/build.sh runs this, then builds the app with it inside.

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent
KEPT = ["proki/assets", "proki/programs/config", "proki/programs/code/work.json"]   # what the engine reads, as it's laid out here

a = Analysis(
    [str(ROOT / "launch.py")],
    pathex        = [str(ROOT)],
    datas         = [(str(ROOT / path), str(Path(path).parent if path.endswith(".json") else path)) for path in KEPT],
    hiddenimports = [*collect_submodules("proki"), "tiktoken_ext", "tiktoken_ext.openai_public"],
    excludes      = ["pytest", "tkinter"],
)
pyz  = PYZ(a.pure)
exe  = EXE(pyz, a.scripts, [], exclude_binaries=True, name="proki-engine", console=True)
coll = COLLECT(exe, a.binaries, a.datas, name="proki-engine")
