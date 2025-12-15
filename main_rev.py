import sys
from pathlib import Path

# Add project root to path to ensure src_rev is importable
ROOT_DIR = Path(__file__).parent.absolute()
sys.path.append(str(ROOT_DIR))

try:
    from src_rev.presentation.dashboard import run_dashboard
except ImportError as e:
    print(f"Error importing application: {e}")
    sys.exit(1)

if __name__ == "__main__":
    run_dashboard()
