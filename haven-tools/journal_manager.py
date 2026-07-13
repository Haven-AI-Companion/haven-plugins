import sys
import json
import os
from datetime import datetime

JOURNAL_FILE = r"C:\Users\admin\haven-server\Personality\journal.json"

def main():
    try:
        raw_input = sys.stdin.read().strip()
        if not raw_input:
            print("Error: Empty input payload.", file=sys.stderr)
            return

        args = json.loads(raw_input)
        operation = args.get("operation", "").lower().strip() # "read" or "write"
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(JOURNAL_FILE), exist_ok=True)

        if operation == "write":
            entry_text = args.get("entry", "").strip()
            if not entry_text:
                print("Error: Entry content is missing for write operation.", file=sys.stderr)
                return
            
            # Load existing
            journal = []
            if os.path.exists(JOURNAL_FILE):
                try:
                    with open(JOURNAL_FILE, "r", encoding="utf-8") as f:
                        journal = json.load(f)
                except Exception:
                    journal = []
            
            # Append new entry
            new_entry = {
                "timestamp": datetime.now().isoformat(),
                "content": entry_text
            }
            journal.append(new_entry)
            
            with open(JOURNAL_FILE, "w", encoding="utf-8") as f:
                json.dump(journal, f, indent=2, ensure_ascii=False)
                
            response = {
                "status": "success",
                "message": "Diary entry written successfully."
            }
            print(json.dumps(response))

        elif operation == "read":
            limit = args.get("limit", 5)
            if not isinstance(limit, int) or limit < 1:
                limit = 5
                
            if not os.path.exists(JOURNAL_FILE):
                print(json.dumps({"status": "success", "entries": []}))
                return
                
            with open(JOURNAL_FILE, "r", encoding="utf-8") as f:
                journal = json.load(f)
            
            # Get latest entries
            latest_entries = journal[-limit:]
            latest_entries.reverse() # Show most recent first
            
            response = {
                "status": "success",
                "entries": latest_entries
            }
            print(json.dumps(response))
        else:
            print(f"Error: Unknown operation '{operation}'", file=sys.stderr)

    except Exception as e:
        print(f"Error executing journal manager: {str(e)}", file=sys.stderr)

if __name__ == "__main__":
    main()
