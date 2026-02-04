import os
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from google import genai
from google.genai import types
from dotenv import load_dotenv

def upload_single_file(client, file_path):
    """Helper function to upload a single file."""
    try:
        file_obj = client.files.upload(file=file_path)
        
        # Wait for processing
        while file_obj.state.name == "PROCESSING":
            time.sleep(1)
            file_obj = client.files.get(name=file_obj.name)
            
        if file_obj.state.name != "ACTIVE":
            return None, f"Failed state: {file_obj.state.name}"
            
        return file_obj, None
    except Exception as e:
        return None, str(e)

def submit_batch():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found.")
        return

    client = genai.Client(api_key=api_key)
    
    # Configuration
    input_dir = "input_images" # Using existing folder
    model_id = "gemini-3-pro-image-preview" # As requested
    # Note: Full resource name usually required for batch matching
    model_id_full = f"models/{model_id}" 

    # 0. User Input for Job Name
    user_job_name = input("Enter a name for this job (optional, press Enter for auto-generated): ").strip()

    # User Input for Configs
    # Candidate Count
    user_candidates = input("Enter candidate count (1-4, default 1): ").strip()
    candidate_count = 1
    if user_candidates:
        try:
            val = int(user_candidates)
            if 1 <= val <= 4:
                candidate_count = val
            else:
                print("Invalid count, using default 1.")
        except ValueError:
            print("Invalid input, using default 1.")
            
    # Image Size
    user_size = input("Enter image size (1K, 2K, 4K, default 1K): ").strip().upper()
    image_size = "1K"
    if user_size in ["1K", "2K", "4K"]:
        image_size = user_size
    elif user_size:
        print("Invalid size, using default 1K.")

    # Save prompt and config to a file for record keeping later
    prompt_text = (
        "Perform a deep color-correction on this underwater image. Apply aggressive color recovery to restore the warm reddish and orange spectrums lost to water depth, specifically neutralizing the dominant cyan/green cast. The seabed (only where present) must be corrected to a natural, earthy brown 'dirt' color. Remove all volumetric haze to make the water appear crystal-clear, but strictly maintain the original background scenery and environment. Do not alter, add, or remove any objects or structural elements in the foreground or background. Ensure 1:1 compositional integrity while sharpening details and removing low-light noise. The result should look like a professional photograph captured with high-powered red-spectrum strobe lighting."
    )
    
    generation_config = {
        "temperature": 0.0,
        "candidate_count": candidate_count, 
        "image_config": {
            "aspect_ratio": "1:1",
            "image_size": image_size
        }
    }

    if not os.path.exists(input_dir):
        print(f"Error: Directory '{input_dir}' not found.")
        return

    # 1. Upload Images
    print(f"Scanning '{input_dir}' for images...")
    image_files = [f for f in os.listdir(input_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
    
    if not image_files:
        print("No images found.")
        return

    uploaded_files = {}
    print(f"Found {len(image_files)} images. Uploading (Concurrent: 10 threads)...")
    
    # Use ThreadPoolExecutor for concurrent uploads
    max_workers = 10
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all upload tasks
        future_to_file = {
            executor.submit(upload_single_file, client, os.path.join(input_dir, img_file)): img_file 
            for img_file in image_files
        }
        
        # Process results as they complete
        completed_count = 0
        total_count = len(image_files)
        
        for future in as_completed(future_to_file):
            img_file = future_to_file[future]
            completed_count += 1
            
            try:
                file_obj, error = future.result()
                if file_obj:
                    uploaded_files[img_file] = file_obj
                    print(f"[{completed_count}/{total_count}] Ready: {img_file}")
                else:
                    print(f"[{completed_count}/{total_count}] Failed {img_file}: {error}")
            except Exception as e:
                print(f"[{completed_count}/{total_count}] Error {img_file}: {e}")

    if not uploaded_files:
        print("No files were successfully uploaded. Aborting.")
        return

    # 2. Prepare Batch Request
    print("\nPreparing batch request...")
    batch_requests = []
    
    # Prompt text is defined above
    
    for img_name, file_obj in uploaded_files.items():
        # Construct the request for this item
        request = {
            "custom_id": img_name, # Use filename as ID to track results
            "request": {
                "model": model_id_full,
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {"text": prompt_text},
                            {"file_data": {"file_uri": file_obj.uri, "mime_type": file_obj.mime_type}}
                        ]
                    }
                ],
                "generation_config": generation_config
            }
        }
        
        batch_requests.append(request)

    # Write JSONL file
    jsonl_filename = "batch_input_images.jsonl"
    with open(jsonl_filename, "w") as f:
        for req in batch_requests:
            f.write(json.dumps(req) + "\n")
            
    print(f"Created {jsonl_filename} with {len(batch_requests)} requests.")

    # 3. Upload JSONL and Create Job
    print("Uploading batch input file...")
    # Upload the JSONL file
    batch_input_file = client.files.upload(
        file=jsonl_filename,
        config={'mime_type': 'application/json'} # Ensure correct mime type for JSONL
    )
    
    print("Creating batch job...")
    try:
        if user_job_name:
            job_display_name = user_job_name
        else:
            timestamp_str = time.strftime("%Y%m%d_%H%M%S")
            job_display_name = f"image_enhance_{timestamp_str}"
        
        job = client.batches.create(
            model=model_id_full,
            src=batch_input_file.name,
            config=types.CreateBatchJobConfig(
                display_name=job_display_name
            )
            # Destination is handled automatically by the API (stored in Cloud Storage/Files API)
        )
        
        print(f"\nBatch Job Created Successfully!")
        print(f"Job ID: {job.name}")
        print(f"Display Name: {job_display_name}")
        print(f"Status: {job.state}")
        print(f"To check status, run: python check_jobs.py")
        print(f"To download results later, run: python download_images.py")
        
        # Save job context to a file for downloading later
        # Use display name if available, otherwise use ID
        folder_name = job_display_name if user_job_name else job.name.split('/')[-1]
        # Clean up name for filesystem (simple sanitization)
        folder_name = "".join(c for c in folder_name if c.isalnum() or c in (' ', '.', '_', '-')).strip().replace(' ', '_')
        
        job_dir = f"generated_images/job_{folder_name}"
        os.makedirs(job_dir, exist_ok=True)
        
        # Save submission request details
        with open(os.path.join(job_dir, "submission_details.json"), "w") as f:
            json.dump({
                "job_id": job.name,
                "display_name": job_display_name,
                "model": model_id_full,
                "prompt": prompt_text,
                "config": generation_config,
                "created_at": str(time.time()),
                "status": str(job.state)
            }, f, indent=2)
            
        print(f"Job details saved to {job_dir}/submission_details.json")
        
    except Exception as e:
        print(f"Error creating batch job: {e}")
        if "INVALID_ARGUMENT" in str(e):
             print("\nTip: This might be due to unsupported generation_config parameters (like aspect_ratio) for this model in Batch mode.")

if __name__ == "__main__":
    submit_batch()
