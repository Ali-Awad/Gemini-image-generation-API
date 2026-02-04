# Gemini Batch Image Generator/Enhancer

A Python-based toolkit for processing large batches of images using Google's Gemini 3 Pro Image model (Batch API). This tool automates the workflow of uploading images, submitting batch enhancement jobs, and organizing the downloaded results.

## Features

- **Batch Processing:** Submit hundreds of images for enhancement in a single job.
- **Concurrent Uploads:** Fast, multi-threaded image uploading (default 10 threads).
- **Cost-Effective:** Uses the Gemini Batch API (50% cheaper than standard requests).
- **Organized Results:** Automatically creates dedicated folders for each job to prevent overwriting.
- **Job Management:** Scripts to check status (with color-coded output) and clean up resources.
- **Customizable:** Configure candidate count and image resolution per job.

## Prerequisites

- Python 3.9+
- A Google Cloud Project with the Gemini API enabled.
- A Gemini API Key.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/gemini-batch-enhancer.git
    cd gemini-batch-enhancer
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment:**
    Create a `.env` file in the root directory and add your API key:
    ```env
    GEMINI_API_KEY=your_actual_api_key_here
    ```

## Usage

### 1. Prepare Inputs
Place your images (`.jpg`, `.png`, `.webp`) in the `input_images/` folder.

### 2. Submit a Batch Job
Run the submission script:
```bash
python submit_image_batch.py
```
- You will be prompted to enter a **Job Name** (optional).
- You can set the **Image Size** (1K, 2K, 4K).
- *Note: Candidate count is currently restricted to 1 for the preview model.*

### 3. Monitor Status
Check the status of your jobs:
```bash
python check_jobs.py
```
- **Green:** Job is Running.
- **Orange:** Job is Pending/Queued.
- **Blue:** Shows your custom Job Name.

### 4. Download Results
Once a job is `SUCCEEDED`, download the images:
```bash
python download_images.py
```
- Enter the Job Name or ID to download specific results.
- Images will be saved in `generated_images/job_[JobName]/`.

### 5. Cleanup (Optional)
To cancel running jobs or delete history/files:
```bash
python cleanup_resources.py
```

## Project Structure

- `submit_image_batch.py`: Main script to upload images and start a batch job.
- `check_jobs.py`: List all active and completed jobs.
- `download_images.py`: Download generated images from completed jobs.
- `cleanup_resources.py`: Utility to cancel jobs and delete storage files.
- `input_images/`: Directory for your source images.
- `generated_images/`: Directory where results are saved.

## Limitations

- **Model:** Currently optimized for `gemini-3-pro-image-preview`.
- **Multiple Candidates:** The current model preview does not support generating multiple images per prompt in batch mode.
- **Storage:** Files uploaded to Gemini storage expire after 48 hours.

## License

[MIT License](LICENSE)
