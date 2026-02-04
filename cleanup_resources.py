import os
import time
from google import genai
from google.genai.types import JobState
from dotenv import load_dotenv

def cleanup_resources():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found.")
        return

    client = genai.Client(api_key=api_key)

    # 1. Stop/Cancel Running Jobs
    print("--- Checking for active jobs to stop ---")
    try:
        # Get all jobs
        jobs = list(client.batches.list())
        
        active_states = [
            "JOB_STATE_QUEUED", 
            "JOB_STATE_PENDING", 
            "JOB_STATE_RUNNING",
            "JOB_STATE_PARTIALLY_SUCCEEDED"
        ]
        
        active_jobs_count = 0
        for job in jobs:
            state_str = str(job.state)
            if state_str in active_states:
                print(f"Cancelling job {job.name} (Status: {state_str})...")
                try:
                    client.batches.cancel(name=job.name)
                    print(f"  > Cancel request sent for {job.name}")
                    active_jobs_count += 1
                except Exception as e:
                    print(f"  > Failed to cancel {job.name}: {e}")
        
        if active_jobs_count == 0:
            print("No active jobs found to stop.")

    except Exception as e:
        print(f"Error checking jobs: {e}")

    # 1.5 Delete Job History (New Feature)
    print("\n--- Job History Cleanup ---")
    try:
        # Re-fetch jobs list (some might have changed state)
        jobs = list(client.batches.list())
        
        if not jobs:
            print("No job history found.")
        else:
            print(f"Found {len(jobs)} total jobs in history.")
            action = input("Delete job history? (all/specific/none): ").strip().lower()
            
            if action == 'all':
                confirm_all = input("Are you sure you want to delete ALL job history? This cannot be undone. (y/n): ")
                if confirm_all.lower() == 'y':
                    for job in jobs:
                        print(f"Deleting job record: {job.name} ({job.state})")
                        try:
                            client.batches.delete(name=job.name)
                            print("  > Deleted.")
                        except Exception as e:
                            print(f"  > Failed to delete: {e}")
            
            elif action == 'specific':
                target_id = input("Enter Job ID or Name to delete (exact match): ").strip()
                if target_id:
                    # Try to find exact match or suffix match
                    matches = []
                    for j in jobs:
                        # Check ID match
                        id_match = (j.name == target_id or j.name.endswith(f"/{target_id}"))
                        # Check Name match (Exact)
                        name_match = False
                        if hasattr(j, 'display_name') and j.display_name:
                            name_match = (j.display_name == target_id)
                        
                        if id_match or name_match:
                            matches.append(j)

                    if matches:
                        for match in matches:
                            print(f"Deleting job record: {match.name}")
                            try:
                                client.batches.delete(name=match.name)
                                print("  > Deleted.")
                            except Exception as e:
                                print(f"  > Failed to delete: {e}")
                    else:
                        print(f"No job found matching '{target_id}'")
            else:
                print("Skipping job history deletion.")

    except Exception as e:
        print(f"Error managing job history: {e}")

    print("\n--- Cleaning up stored files ---")
    # 2. Delete All Files
    delete_files = input("Delete all uploaded files from storage? (y/n): ").strip().lower()
    
    if delete_files == 'y':
        try:
            # The list method for files might be paginated, so converting to list gets all
            files = list(client.files.list())
            
            if not files:
                print("No files found to delete.")
            else:
                print(f"Found {len(files)} file(s). Deleting...")
                for f in files:
                    print(f"Deleting file: {f.name} (Display Name: {f.display_name})")
                    try:
                        client.files.delete(name=f.name)
                        print("  > Deleted.")
                    except Exception as e:
                        print(f"  > Failed to delete {f.name}: {e}")
                        
        except Exception as e:
            print(f"Error checking files: {e}")
    else:
        print("Skipping file cleanup.")

if __name__ == "__main__":
    print("WARNING: This script manages cleanup of Jobs and Files.")
    confirm = input("Continue? (y/n): ")
    if confirm.lower() == 'y':
        cleanup_resources()
    else:
        print("Operation cancelled.")
