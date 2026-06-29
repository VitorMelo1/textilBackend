import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
CORE_API_ROOT = BACKEND_ROOT / "core-api"

sys.path.insert(0, str(BACKEND_ROOT))
sys.path.insert(0, str(CORE_API_ROOT))
