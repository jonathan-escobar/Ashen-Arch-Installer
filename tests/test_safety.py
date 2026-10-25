"""Static fail-closed checks: complementary to runtime validation."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
ui = (root / 'overlay/opt/ashen-installer/main.py').read_text()
helper = (root / 'overlay/usr/local/bin/ashen-install').read_text()
core = (root / 'overlay/opt/ashen-installer/install_core.py').read_text()
assert 'BORRAR {plan.disk}' in ui
assert 'plan.confirmation != f"BORRAR {plan.disk}"' in core
assert 'preflight(plan, root=True)' in core
assert 'subprocess.run(argv' in core
assert 'shell=True' not in core
assert '--execute' in helper
print('Safety structure checks passed')
