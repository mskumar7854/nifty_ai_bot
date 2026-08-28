import sys
from pathlib import Path
import logging

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

WORKSPACE = Path(r"c:\Users\Selva\Downloads\nifty-ai-system")
sys.path.insert(0, str(WORKSPACE))

from core.shadow_variant_runner import ShadowVariantRunner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backfill")

def main():
    print("=" * 60)
    print("🔄 SHADOW VARIANT BACKFILL")
    print("=" * 60)
    
    runner = ShadowVariantRunner()
    print(f"Loaded {len(runner.variants)} variants.")
    
    print("Starting backfill from decision_snapshots_v2...")
    processed, inserted = runner.backfill_from_db()
    
    print(f"\n✅ Backfill complete.")
    print(f"Processed snapshots: {processed}")
    print(f"Inserted variant records: {inserted} (should be {processed} x {len(runner.variants)} = {processed * len(runner.variants)})")
    
if __name__ == "__main__":
    main()
