import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

def check_jobs():
    # Load environment variables
    load_dotenv()
    
    RED = '\033[91m'
    GREEN = '\033[92m'
    RESET = '\033[0m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    ORANGE = '\033[38;5;208m'
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment variables.")
        return

    # Configure the client
    client = genai.Client(api_key=api_key)

    print("Checking for batch jobs...")
    
    try:
        # List batch jobs
        # We can use the pager to iterate through all jobs
        jobs_iterator = client.batches.list()
        
        # Convert to list to analyze
        jobs = list(jobs_iterator)
        
        if not jobs:
            print("No batch jobs found (active or history).")
            return

        # Filter for active jobs
        active_states = [
            "JOB_STATE_PENDING", 
            "JOB_STATE_QUEUED", 
            "JOB_STATE_RUNNING", 
            "JOB_STATE_UPDATING",
            "JOB_STATE_PAUSED",
            "JOB_STATE_CANCELLING"
        ]
        
        active_jobs = [j for j in jobs if j.state in active_states]
        completed_jobs = [j for j in jobs if j.state not in active_states]

        print(f"\nSummary: {GREEN}{len(active_jobs)} active{RESET}, {len(completed_jobs)} completed/failed.")
        
        if active_jobs:
            print(f"\n=== {GREEN}ACTIVE JOBS{RESET} ===")
            for job in active_jobs:
                print(f"Job ID: {job.name}")
                if hasattr(job, 'display_name') and job.display_name:
                    print(f"Name: {BLUE}{job.display_name}{RESET}")
                
                # Determine state color
                state_str = str(job.state)
                if state_str == "JOB_STATE_RUNNING":
                     state_display = f"{GREEN}{state_str}{RESET}"
                elif state_str in ["JOB_STATE_PENDING", "JOB_STATE_QUEUED"]:
                     state_display = f"{ORANGE}{state_str}{RESET}"
                else:
                     state_display = state_str
                     
                print(f"Status: {state_display}")
                print(f"Created: {job.create_time}")
                print("-" * 30)
        else:
            print("\nNo active (running/pending) jobs.")

        if completed_jobs:
            print(f"\n=== {RED}RECENT HISTORY (Last 5){RESET} ===")
            # Sort by create_time descending just in case
            completed_jobs.sort(key=lambda x: str(x.create_time), reverse=True)
            
            for job in completed_jobs[:5]:
                print(f"Job ID: {job.name}")
                if hasattr(job, 'display_name') and job.display_name:
                    print(f"Name: {job.display_name}")
                print(f"Status: {job.state}")
                print(f"Created: {job.create_time}")
                if hasattr(job, 'error') and job.error:
                     print(f"Error: {job.error}")
                print("-" * 30)

    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_jobs()
