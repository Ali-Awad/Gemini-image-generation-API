import os
import json
import base64
from google import genai
from dotenv import load_dotenv

def download_images():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    
    # Base output directory
    base_output_dir = "generated_images"
    os.makedirs(base_output_dir, exist_ok=True)

    print("Checking for completed batch jobs...")
    try:
        jobs = list(client.batches.list())
        
        # User Filter
        target_input = input("Enter specific Job ID or Name to download (or press Enter to scan all): ").strip()
        
        if target_input:
            # Filter matches (support both full name "batches/xyz", short id "xyz", and display name)
            filtered_jobs = []
            for j in jobs:
                # Check ID match
                id_match = (j.name == target_input or j.name.endswith(f"/{target_input}"))
                # Check Display Name match (EXACT match only)
                name_match = False
                if hasattr(j, 'display_name') and j.display_name:
                    name_match = (target_input == j.display_name)
                
                if (id_match or name_match) and j.state == "JOB_STATE_SUCCEEDED":
                    filtered_jobs.append(j)
            
            completed_jobs = filtered_jobs
            
            if not completed_jobs:
                 print(f"No completed job found matching '{target_input}'")
                 return
        else:
            completed_jobs = [j for j in jobs if j.state == "JOB_STATE_SUCCEEDED"]
        
        if not completed_jobs:
            print("No completed batch jobs found.")
            return

        print(f"Found {len(completed_jobs)} completed job(s). Processing...")

        for job in completed_jobs:
            print(f"\nJob: {job.name}")
            if hasattr(job, 'display_name') and job.display_name:
                print(f"Name: {job.display_name}")
            
            # Determine folder name
            # Prefer display name if available, otherwise ID
            if hasattr(job, 'display_name') and job.display_name and not job.display_name.startswith("image_enhance_"):
                 # Use user-provided name (sanitize it)
                 folder_name = job.display_name
            else:
                 # Use ID for auto-generated names or missing names
                 folder_name = job.name.split('/')[-1]
            
            # Sanitize folder name
            folder_name = "".join(c for c in folder_name if c.isalnum() or c in (' ', '.', '_', '-')).strip().replace(' ', '_')
            
            job_output_dir = os.path.join(base_output_dir, f"job_{folder_name}")
            
            # Check if this job has already been processed (folder exists and has images)
            if os.path.exists(job_output_dir):
                # Simple check: if there are image files in it, we assume it's done.
                existing_files = [f for f in os.listdir(job_output_dir) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
                if existing_files:
                    print(f"  Skipping: Output folder already exists with {len(existing_files)} images.")
                    continue
            
            # If directory exists and has images, we might want to skip or check
            # For now, we will process it to ensure we have the files.
            os.makedirs(job_output_dir, exist_ok=True)
            
            if not job.dest or not job.dest.file_name:
                print("  No output file found.")
                continue

            print(f"  Downloading results: {job.dest.file_name}")
            try:
                content = client.files.download(file=job.dest.file_name)
                
                # Parse JSONL
                lines = content.decode('utf-8').strip().split('\n')
                
                for line in lines:
                    try:
                        item = json.loads(line)
                        custom_id = item.get('custom_id', f"unknown_{lines.index(line)}")
                        
                        # Check for error in individual request
                        if 'error' in item:
                            print(f"  Error for {custom_id}: {item['error']['message']}")
                            continue
                            
                        # Extract image
                        # Structure: response -> candidates[0] -> content -> parts[0] -> inline_data -> data
                        response = item.get('response', {})
                        candidates = response.get('candidates', [])
                        
                        if not candidates:
                            print(f"  No candidates returned for {custom_id}")
                            continue
                            
                        parts = candidates[0].get('content', {}).get('parts', [])
                        if not parts:
                            print(f"  No content parts for {custom_id}")
                            continue
                            
                        # Look for image data
                        image_data = None
                        
                        # Loop through all candidates
                        for i, candidate in enumerate(candidates):
                            parts = candidate.get('content', {}).get('parts', [])
                            if not parts:
                                continue
                                
                            img_data_b64 = None
                            for part in parts:
                                if 'inline_data' in part:
                                    img_data_b64 = part['inline_data']['data']
                                    break
                                elif 'inlineData' in part:
                                    img_data_b64 = part['inlineData']['data']
                                    break
                            
                            if img_data_b64:
                                # Determine filename
                                # If there's only 1 candidate, keep original name.
                                # If multiple, append _c1, _c2, etc.
                                if len(candidates) > 1:
                                    name_parts = os.path.splitext(custom_id)
                                    final_filename = f"{name_parts[0]}_c{i+1}{name_parts[1]}"
                                else:
                                    final_filename = custom_id
                                
                                # Decode and save
                                img_bytes = base64.b64decode(img_data_b64)
                                
                                # Construct full path including subfolders
                                # Ensure custom_id uses local OS separators
                                local_filename = final_filename.replace('/', os.sep)
                                save_path = os.path.join(job_output_dir, local_filename)
                                
                                # Create parent directory if it doesn't exist
                                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                                
                                with open(save_path, "wb") as img_f:
                                    img_f.write(img_bytes)
                                print(f"  Saved: {save_path}")
                            else:
                                print(f"  No image found in candidate {i+1} for {custom_id}")
                            
                    except json.JSONDecodeError:
                        print("  Failed to parse JSON line.")
                    except Exception as e:
                        print(f"  Error processing item {custom_id}: {e}")
                        
            except Exception as e:
                print(f"  Error downloading/processing file: {e}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    download_images()
