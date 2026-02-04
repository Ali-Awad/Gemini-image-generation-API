import os
from google import genai
from dotenv import load_dotenv
from datetime import datetime, timezone

def format_size(size_bytes):
    if not size_bytes:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def check_storage():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found.")
        return

    client = genai.Client(api_key=api_key)

    print("Checking uploaded files and storage usage...")
    print("-" * 60)

    try:
        files = list(client.files.list())
        
        if not files:
            print("No files found in storage.")
            return

        total_size = 0
        active_files = 0
        
        # Header
        print(f"{'Display Name':<30} | {'Size':<10} | {'State':<10} | {'Expires In'}")
        print("-" * 60)

        now = datetime.now(timezone.utc)

        for f in files:
            size = f.size_bytes or 0
            total_size += size
            active_files += 1
            
            # Calculate time until expiration
            expires_in = "N/A"
            if f.expiration_time:
                # Ensure we handle timezone aware datetimes
                exp_time = f.expiration_time
                if exp_time.tzinfo is None:
                    exp_time = exp_time.replace(tzinfo=timezone.utc)
                
                delta = exp_time - now
                if delta.total_seconds() > 0:
                    hours = int(delta.total_seconds() // 3600)
                    minutes = int((delta.total_seconds() % 3600) // 60)
                    expires_in = f"{hours}h {minutes}m"
                else:
                    expires_in = "Expired"

            name = f.display_name or f.name
            # Truncate long names
            if len(name) > 28:
                name = name[:25] + "..."
                
            print(f"{name:<30} | {format_size(size):<10} | {f.state.name if f.state else 'UNKNOWN':<10} | {expires_in}")

        print("-" * 60)
        print(f"Total Files: {active_files}")
        print(f"Total Storage Used: {format_size(total_size)}")
        print("\nNote: Files automatically expire after 48 hours.")

    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_storage()
