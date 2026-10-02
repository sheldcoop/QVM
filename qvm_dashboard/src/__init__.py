"""QVM Dashboard core module.

Deliberately import-free: chart-only consumers (e.g. `from src import theme`)
must not pay for pandas and the full parser. Import submodules directly
(`from src.parser import ...`, `from src.theme import ...`).
"""
