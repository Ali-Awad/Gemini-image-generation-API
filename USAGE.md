# Gemini API Batch Usage Documentation

This document summarizes key information about managing batch jobs, files, storage, and billing for the Google Gemini API, based on the `google-genai` Python SDK.

## 1. Batch Jobs

### Checking Job Status
To check for running or pending jobs:
```bash
python check_jobs.py
```
- **Active Jobs:** Jobs with status `QUEUED`, `PENDING` (Orange), or `RUNNING` (Green).
- **History:** Jobs with status `SUCCEEDED`, `FAILED`, or `CANCELLED`.
- **Note:** `client.batches.list()` returns **all** jobs associated with your API key history.

### Submitting Jobs
To submit a new batch job for image enhancement:
```bash
python submit_image_batch.py
```
- **Inputs:** Scans `input_images/` folder.
- **Concurrent Uploads:** Uses 10 parallel threads for faster file uploading.
- **Configuration:** Prompts for:
    - **Job Name:** Custom display name (e.g., "4k_run").
    - **Candidate Count:** Number of images to generate (Default: 1).
    - **Image Size:** Output resolution (1K, 2K, 4K).
- **Context:** Saves submission details (prompt, config) to `generated_images/job_{id}/submission_details.json`.

### Downloading Results
To download results from completed (`SUCCEEDED`) jobs:
```bash
python download_images.py
```
- **Interactive:** Asks for a specific Job ID or Name (exact match). Press Enter to download all new jobs.
- **Output:** Saves images to `generated_images/job_{id}/` to prevent overwriting.
- **Naming:** Appends `_c1`, `_c2` etc. if multiple candidates are generated.
- **Skip Logic:** Skips downloading if the output folder already exists and contains images.

### Job States (Official SDK Constants)
- `JOB_STATE_PENDING`: Job is created but waiting to be scheduled.
- `JOB_STATE_QUEUED`: Job is scheduled and waiting for resources.
- `JOB_STATE_RUNNING`: Job is currently processing.
- `JOB_STATE_SUCCEEDED`: Job completed successfully.
- `JOB_STATE_FAILED`: Job failed (see error code).
- `JOB_STATE_CANCELLED`: Job was manually stopped.

## 2. File Storage & Management

### Storage Limits
- **Total Storage:** 20 GB per project.
- **File Size Limit:** 2 GB per file.
- **File Retention:** Files uploaded via the File API are temporary and **auto-expire after 48 hours**.

### Checking Storage
To check current storage usage and orphaned files:
```bash
python check_storage.py
```

### Cleanup
To manage resources:
```bash
python cleanup_resources.py
```
- **Options:** 
    - Cancel running jobs.
    - Delete job history (All or Specific by ID/Name).
    - Delete all uploaded files.

## 3. Known Limitations & Issues

### Model: `gemini-3-pro-image-preview`
1.  **Multiple Candidates:** 
    - **Status:** **NOT ENABLED**. Setting `candidate_count > 1` will cause the job to fail with `"Multiple candidates is not enabled for this model"`.
    - **Workaround:** To generate multiple variations, you must submit multiple request lines for the same image in the batch file (not currently automated by the script).
    
2.  **Configuration:**
    - `aspect_ratio` and `image_size` **MUST** be nested inside `image_config` within `generation_config`.
    - `response_mime_type` is **not supported** in the batch configuration for this model.

3.  **Batch API:**
    - **Deduplication:** The API does **not** deduplicate file uploads. Submitting the same file twice creates two entries in storage.
    - **Cost:** You are billed for successful generations even if the inputs were duplicates.

## 4. Billing & Costs

### Failed Requests
- **No Charge:** You are **not charged** for requests that result in a client-side error (e.g., `400 Bad Request`, `Invalid Argument`), as no tokens are generated.
- **Partial Batches:** If a batch has mixed results, you are billed only for the successful items.

### Storage Costs
- File storage for the Gemini API is currently **free** (within the 20 GB limit).

## 5. Rate Limits & Quotas

### Batch Specific Limits
- **Concurrent Jobs:** Up to **100** active batch jobs.
- **Throughput:** Batch processing is asynchronous and does not consume your standard RPM/TPM quotas.
- **Uploads:** File uploads (Phase 1) **DO** count against standard File API rate limits.

## 6. Environment Setup

### Prerequisites
- Python 3.9+
- Google GenAI SDK (`google-genai`)

### Setup
1. Create a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set your API key in `.env`:
   ```
   GEMINI_API_KEY=your_api_key_here
   ```
