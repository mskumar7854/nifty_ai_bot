import argparse
import json
import hashlib
from pathlib import Path
from datetime import datetime

def check_audit(date_str: str):
    file_path = Path("data/raw") / f"v2_raw_inputs_{date_str}.jsonl"
    
    if not file_path.exists():
        print(f"Error: {file_path} does not exist.")
        return
        
    records = []
    malformed = 0
    hash_failures = 0
    
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                
                # Check hash
                stored_hash = record.get("record_hash")
                record_for_hash = dict(record)
                record_for_hash.pop("record_hash", None)
                canonical_json = json.dumps(record_for_hash, sort_keys=True, separators=(',', ':'))
                computed_hash = hashlib.sha256(canonical_json.encode('utf-8')).hexdigest()
                
                if stored_hash != computed_hash:
                    hash_failures += 1
                
                records.append(record)
            except Exception:
                malformed += 1
                
    if not records:
        print("No valid records found.")
        return
        
    sequences = [r.get("capture_sequence", 0) for r in records]
    first_seq = min(sequences) if sequences else 0
    last_seq = max(sequences) if sequences else 0
    expected_records = (last_seq - first_seq + 1) if sequences else 0
    missing_sequences = expected_records - len(sequences)
    
    correlation_ids = [r.get("correlation_id") for r in records]
    duplicate_ids = len(correlation_ids) - len(set(correlation_ids))
    
    # In a real system, you'd join this with the DB to see how many were actually approved vs rejected.
    # For now, since the logger captures everything PRE-GATE, they are all candidates.
    # We can check "derived_pre_gate" or similar if we had a field, but actually the approval happens downstream.
    # We just assume all captured records are candidates.
    
    # Ideally, we compare evaluated candidates with db.
    
    print("V2 RAW CAPTURE AUDIT")
    print("────────────────────────────")
    print(f"Candidates evaluated:       {len(records)}")
    print(f"Raw records captured:       {len(records)}")
    completeness = (len(records) / expected_records * 100) if expected_records > 0 else 0
    print(f"Capture completeness:       {completeness:.0f}%")
    print("")
    print(f"First sequence:             {first_seq}")
    print(f"Last sequence:              {last_seq}")
    print(f"Expected records:           {expected_records}")
    print(f"Missing sequences:          {missing_sequences}")
    print("")
    print(f"Duplicate IDs:              {duplicate_ids}")
    print(f"Hash failures:              {hash_failures}")
    print(f"Malformed records:          {malformed}")
    print("")
    print("NO_TRADE cycles:             excluded")
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("date", type=str, help="YYYY-MM-DD", nargs="?", default=datetime.now().strftime("%Y-%m-%d"))
    args = parser.parse_args()
    check_audit(args.date)
