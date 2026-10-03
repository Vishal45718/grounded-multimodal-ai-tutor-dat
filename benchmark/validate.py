import json
import sqlite3
import os
import sys

def main():
    cases_path = "benchmark/cases.jsonl"
    if not os.path.exists(cases_path):
        print("cases.jsonl not found.")
        sys.exit(1)

    db_path = "data/corpus.db"
    
    # We allow the DB to not exist or be empty if it's just a validation in a pure CI env, 
    # but the prompt says: "referenced evidence IDs exist where the repository can verify them"
    # So we'll check against the DB if it exists.
    valid_chunks = set()
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT chunk_id FROM chunks")
            valid_chunks = {row[0] for row in cursor.fetchall()}
            conn.close()
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            sys.exit(1)

    cases = []
    with open(cases_path, "r") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                cases.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"Invalid JSON on line {line_num}")
                sys.exit(1)

    if len(cases) != 20:
        print(f"Error: Expected exactly 20 cases, got {len(cases)}")
        sys.exit(1)

    ids = set()
    visual_count = 0
    
    required_fields = {
        "id", "question", "category", "expected_answer", 
        "expected_evidence_ids", "expected_source_id", 
        "expected_version_id", "answerability", 
        "visual_required", "adversarial_type", "notes"
    }

    valid_answerabilities = {"answerable", "partial", "unanswerable"}

    for i, case in enumerate(cases):
        # Unique IDs
        if case.get("id") in ids:
            print(f"Error: Duplicate ID {case.get('id')} at index {i}")
            sys.exit(1)
        ids.add(case.get("id"))

        # Required fields
        missing_fields = required_fields - set(case.keys())
        if missing_fields:
            print(f"Error: Case {case.get('id')} missing fields: {missing_fields}")
            sys.exit(1)

        # Answerability
        if case["answerability"] not in valid_answerabilities:
            print(f"Error: Case {case.get('id')} has invalid answerability: {case['answerability']}")
            sys.exit(1)

        # Visual checking
        if case["visual_required"]:
            visual_count += 1
            if not case["notes"]:
                print(f"Error: Visual case {case.get('id')} must have explanatory notes")
                sys.exit(1)
        
        # Evidence checking
        if case["answerability"] in ["answerable", "partial"]:
            if not case["expected_evidence_ids"]:
                print(f"Error: Answerable/partial case {case.get('id')} must have expected_evidence_ids")
                sys.exit(1)
            if not case["expected_source_id"] or not case["expected_version_id"]:
                print(f"Error: Answerable/partial case {case.get('id')} must have expected_source_id and expected_version_id")
                sys.exit(1)
            
            # Check if referenced evidence IDs exist
            if valid_chunks:
                for eid in case["expected_evidence_ids"]:
                    if eid not in valid_chunks:
                        print(f"Error: Evidence ID {eid} for case {case.get('id')} does not exist in the database.")
                        sys.exit(1)
        elif case["answerability"] == "unanswerable":
            if case["expected_evidence_ids"]:
                print(f"Error: Unanswerable case {case.get('id')} must NOT have expected_evidence_ids")
                sys.exit(1)

    if visual_count < 5:
        print(f"Error: Expected at least 5 visual_required=true cases, got {visual_count}")
        sys.exit(1)

    print("Validation passed successfully.")

if __name__ == "__main__":
    main()
