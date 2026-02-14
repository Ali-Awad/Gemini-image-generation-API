import os
import json
import base64
import shutil
import tempfile
import urllib.request
from urllib.error import HTTPError, URLError
from google import genai
from dotenv import load_dotenv

# Chunk size for streaming download (avoid loading entire file into RAM)
STREAM_CHUNK_SIZE = 1024 * 1024  # 1 MiB
PROGRESS_INTERVAL = 200  # Print progress every N images

# Where to find source images for failed items (must match submit_image_batch input_dir)
INPUT_BASE_DIR = "input_images"

# Marker file to track temp path so we can detect/clean leftover from interrupted runs
_TEMP_MARKER = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), ".download_images_temp"
)


def _check_clean_previous_temp() -> None:
    """If a previous run left a temp file (e.g. script was killed), report and remove it."""
    if not os.path.isfile(_TEMP_MARKER):
        return
    try:
        with open(_TEMP_MARKER, "r") as f:
            prev_path = f.read().strip()
    except OSError:
        prev_path = ""
    try:
        os.unlink(_TEMP_MARKER)
    except OSError:
        pass
    if not prev_path:
        return
    if os.path.isfile(prev_path):
        try:
            os.unlink(prev_path)
            print(f"Removed leftover temp file from previous run: {prev_path}")
        except OSError as e:
            print(f"Could not remove leftover temp file {prev_path}: {e}")
    else:
        print("Previous run's temp file was already deleted (clean exit).")


# Known finish_reason values (Gemini API) for clearer logs
FINISH_REASONS = {
    0: "FINISH_REASON_UNSPECIFIED",
    1: "STOP",
    2: "MAX_TOKENS",
    3: "SAFETY",
    4: "RECITATION",
    5: "OTHER",
}


def _format_response_reason(response: dict, candidate: dict | None = None) -> str:
    """Build a short reason string from API response/candidate for empty content."""
    parts = []
    if candidate is not None:
        fr = candidate.get("finish_reason") or candidate.get("finishReason")
        if fr is not None:
            parts.append(f"finish_reason={FINISH_REASONS.get(fr, fr)}")
        safety = candidate.get("safety_ratings") or candidate.get("safetyRatings")
        if safety:
            parts.append(f"safety_ratings={safety}")
    prompt_fb = response.get("prompt_feedback") or response.get("promptFeedback")
    if prompt_fb:
        parts.append(f"prompt_feedback={prompt_fb}")
    return "; ".join(parts) if parts else "no reason in response"


def _copy_failed_to_unprocessed(
    custom_id: str, job_output_dir: str, input_base_dir: str
) -> None:
    """Copy the source image for a failed item into job_output_dir/unprocessed, preserving path structure."""
    if not custom_id or custom_id.startswith("unknown_"):
        return
    src_path = os.path.join(
        input_base_dir, custom_id.replace("/", os.sep)
    )
    if not os.path.isfile(src_path):
        return
    unprocessed_dir = os.path.join(job_output_dir, "unprocessed")
    dest_path = os.path.join(
        unprocessed_dir, custom_id.replace("/", os.sep)
    )
    try:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy2(src_path, dest_path)
    except OSError:
        pass


def _stream_download_to_file(api_key: str, file_name: str, dest_path: str) -> None:
    """Download file from Gemini API to disk in chunks to avoid OOM on large batches."""
    name = file_name if file_name.startswith("files/") else f"files/{file_name}"
    path = f"{name}:download"
    url = f"https://generativelanguage.googleapis.com/v1beta/{path}?alt=media"
    req = urllib.request.Request(url, headers={"x-goog-api-key": api_key})
    try:
        print("  Streaming to disk (this may take several minutes for large batches)...")
        with urllib.request.urlopen(req, timeout=3600) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Download failed with status {resp.status}")
            total_bytes = 0
            progress_interval_mb = 25  # Print every 25 MiB (more frequent feedback)
            next_report_mb = progress_interval_mb
            with open(dest_path, "wb") as f:
                while True:
                    chunk = resp.read(STREAM_CHUNK_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
                    total_bytes += len(chunk)
                    total_mb = total_bytes / (1024 * 1024)
                    if total_mb >= next_report_mb:
                        print(f"  ... downloaded {total_mb:.0f} MiB")
                        next_report_mb += progress_interval_mb
            if total_bytes > 0 and (total_bytes / (1024 * 1024)) < progress_interval_mb:
                print(f"  ... downloaded {total_bytes / (1024 * 1024):.1f} MiB")
    except HTTPError as e:
        raise RuntimeError(f"Download failed: {e.code} {e.reason}") from e
    except URLError as e:
        raise RuntimeError(f"Download failed: {e.reason}") from e


def download_images():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    
    # Base output directory
    base_output_dir = "generated_images"
    os.makedirs(base_output_dir, exist_ok=True)

    _check_clean_previous_temp()

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
            tmp_path = None
            try:
                # Stream download to temp file to avoid OOM on large batches (e.g. 4000+ images)
                with tempfile.NamedTemporaryFile(
                    mode="wb", suffix=".jsonl", delete=False
                ) as tmp:
                    tmp_path = tmp.name
                try:
                    with open(_TEMP_MARKER, "w") as mf:
                        mf.write(tmp_path)
                    _stream_download_to_file(
                        api_key, job.dest.file_name, tmp_path
                    )
                except Exception as e:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                    try:
                        os.unlink(_TEMP_MARKER)
                    except OSError:
                        pass
                    raise e

                saved_count = 0
                # Process JSONL line by line so we never load the whole file into memory
                with open(tmp_path, "r", encoding="utf-8") as f:
                    for line_num, line in enumerate(f):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            item = json.loads(line)
                            custom_id = item.get(
                                "custom_id", f"unknown_{line_num}"
                            )

                            # Check for error in individual request
                            if "error" in item:
                                print(
                                    f"  Error for {custom_id}: {item['error']['message']}"
                                )
                                _copy_failed_to_unprocessed(
                                    custom_id, job_output_dir, INPUT_BASE_DIR
                                )
                                continue

                            # Extract image
                            response = item.get("response", {})
                            candidates = response.get("candidates", [])

                            if not candidates:
                                reason = _format_response_reason(response, None)
                                print(
                                    f"  No candidates returned for {custom_id} ({reason})"
                                )
                                _copy_failed_to_unprocessed(
                                    custom_id, job_output_dir, INPUT_BASE_DIR
                                )
                                continue

                            parts = (
                                candidates[0]
                                .get("content", {})
                                .get("parts", [])
                            )
                            if not parts:
                                reason = _format_response_reason(
                                    response, candidates[0]
                                )
                                print(
                                    f"  No content parts for {custom_id} ({reason})"
                                )
                                _copy_failed_to_unprocessed(
                                    custom_id, job_output_dir, INPUT_BASE_DIR
                                )
                                continue

                            # Loop through all candidates
                            for i, candidate in enumerate(candidates):
                                parts = (
                                    candidate.get("content", {})
                                    .get("parts", [])
                                )
                                if not parts:
                                    continue

                                img_data_b64 = None
                                for part in parts:
                                    if "inline_data" in part:
                                        img_data_b64 = part["inline_data"][
                                            "data"
                                        ]
                                        break
                                    elif "inlineData" in part:
                                        img_data_b64 = part["inlineData"][
                                            "data"
                                        ]
                                        break

                                if img_data_b64:
                                    if len(candidates) > 1:
                                        name_parts = os.path.splitext(
                                            custom_id
                                        )
                                        final_filename = (
                                            f"{name_parts[0]}_c{i+1}{name_parts[1]}"
                                        )
                                    else:
                                        final_filename = custom_id

                                    img_bytes = base64.b64decode(img_data_b64)

                                    local_filename = final_filename.replace(
                                        "/", os.sep
                                    )
                                    save_path = os.path.join(
                                        job_output_dir, local_filename
                                    )

                                    parent = os.path.dirname(save_path)
                                    if parent:
                                        os.makedirs(parent, exist_ok=True)

                                    with open(save_path, "wb") as img_f:
                                        img_f.write(img_bytes)
                                    saved_count += 1
                                    if saved_count <= 10 or saved_count % PROGRESS_INTERVAL == 0:
                                        print(
                                            f"  Saved {saved_count}: {save_path}"
                                        )
                                else:
                                    reason = _format_response_reason(
                                        response, candidate
                                    )
                                    print(
                                        f"  No image found in candidate {i+1} for {custom_id} ({reason})"
                                    )
                                    _copy_failed_to_unprocessed(
                                        custom_id, job_output_dir, INPUT_BASE_DIR
                                    )
                        except json.JSONDecodeError:
                            print("  Failed to parse JSON line.")
                        except Exception as e:
                            print(
                                f"  Error processing item {custom_id}: {e}"
                            )

                os.unlink(tmp_path)
                try:
                    os.unlink(_TEMP_MARKER)
                except OSError:
                    pass
                print(f"  Done. Total images saved: {saved_count}")

            except Exception as e:
                print(f"  Error downloading/processing file: {e}")
            finally:
                if tmp_path is not None:
                    try:
                        os.unlink(tmp_path)
                    except OSError:
                        pass
                try:
                    os.unlink(_TEMP_MARKER)
                except OSError:
                    pass

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    download_images()
