const API_BASE = ""; // same-origin; set to e.g. "http://localhost:8000" if serving frontend separately

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const dropzoneIdle = document.getElementById("dropzone-idle");
const dropzoneSelected = document.getElementById("dropzone-selected");
const preview = document.getElementById("preview");
const selectedFilename = document.getElementById("selected-filename");
const changeFileBtn = document.getElementById("change-file");
const submitBtn = document.getElementById("submit-btn");

const uploadPanel = document.getElementById("upload-panel");
const progressPanel = document.getElementById("progress-panel");
const resultPanel = document.getElementById("result-panel");
const errorPanel = document.getElementById("error-panel");

const progressLabel = document.getElementById("progress-label");
const progressPct = document.getElementById("progress-pct");
const progressFill = document.getElementById("progress-fill");
const progressDetail = document.getElementById("progress-detail");

const resultVideo = document.getElementById("result-video");
const downloadLink = document.getElementById("download-link");
const restartBtn = document.getElementById("restart-btn");

const errorMessage = document.getElementById("error-message");
const errorRetry = document.getElementById("error-retry");

let selectedFile = null;
let pollTimer = null;

const MAX_BYTES = 500 * 1024 * 1024; // 500MB

// ---- File selection ----

dropzone.addEventListener("click", () => fileInput.click());

dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("dragover");
});
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
});

fileInput.addEventListener("change", () => {
  if (fileInput.files.length) handleFile(fileInput.files[0]);
});

changeFileBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  resetSelection();
});

function handleFile(file) {
  if (!file.type.startsWith("video/")) {
    showError("That file doesn't look like a video. Try an MP4, MOV or WEBM.");
    return;
  }
  if (file.size > MAX_BYTES) {
    showError("That file is over the 500MB limit.");
    return;
  }

  selectedFile = file;
  selectedFilename.textContent = `${file.name} — ${(file.size / (1024 * 1024)).toFixed(1)} MB`;
  preview.src = URL.createObjectURL(file);

  dropzoneIdle.hidden = true;
  dropzoneSelected.hidden = false;
  submitBtn.disabled = false;
}

function resetSelection() {
  selectedFile = null;
  fileInput.value = "";
  preview.src = "";
  dropzoneIdle.hidden = false;
  dropzoneSelected.hidden = true;
  submitBtn.disabled = true;
}

// ---- Submit / upload ----

submitBtn.addEventListener("click", async () => {
  if (!selectedFile) return;

  showPanel("progress");
  setProgress(0, "Uploading", "Sending your video to the server.");

  try {
    const formData = new FormData();
    formData.append("file", selectedFile);

    const res = await fetch(`${API_BASE}/api/upload`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) throw new Error(`Upload failed (${res.status})`);

    const { job_id } = await res.json();
    pollJob(job_id);
  } catch (err) {
    showError(err.message || "Upload failed. Check your connection and try again.");
  }
});

// ---- Poll job status ----

function pollJob(jobId) {
  pollTimer = setInterval(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/jobs/${jobId}`);
      if (!res.ok) throw new Error(`Lost track of the job (${res.status})`);

      const job = await res.json();
      handleJobUpdate(job);
    } catch (err) {
      clearInterval(pollTimer);
      showError(err.message || "Lost connection while checking progress.");
    }
  }, 2000);
}

function handleJobUpdate(job) {
  // Expected job.status: "queued" | "detecting" | "inpainting" | "encoding" | "done" | "failed"
  switch (job.status) {
    case "queued":
      setProgress(5, "Queued", "Waiting for a worker to pick this up.");
      break;
    case "detecting":
      setProgress(job.progress ?? 20, "Detecting text", "Finding text regions in each frame.");
      break;
    case "inpainting":
      setProgress(job.progress ?? 55, "Removing text", "Reconstructing the frames underneath.");
      break;
    case "encoding":
      setProgress(job.progress ?? 90, "Encoding", "Stitching frames back into video.");
      break;
    case "done":
      clearInterval(pollTimer);
      setProgress(100, "Done", "");
      showResult(job.result_url);
      break;
    case "failed":
      clearInterval(pollTimer);
      showError(job.error || "Processing failed on the server.");
      break;
  }
}

function setProgress(pct, label, detail) {
  progressFill.style.width = `${pct}%`;
  progressPct.textContent = `${pct}%`;
  progressLabel.textContent = label;
  progressDetail.textContent = detail;
}

// ---- Result ----

function showResult(resultUrl) {
  resultVideo.src = resultUrl;
  downloadLink.href = resultUrl;
  showPanel("result");
}

restartBtn.addEventListener("click", () => {
  resetSelection();
  showPanel("upload");
});

// ---- Error ----

function showError(message) {
  errorMessage.textContent = message;
  showPanel("error");
}

errorRetry.addEventListener("click", () => {
  showPanel("upload");
});

// ---- Panel switching ----

function showPanel(name) {
  uploadPanel.hidden = name !== "upload";
  progressPanel.hidden = name !== "progress";
  resultPanel.hidden = name !== "result";
  errorPanel.hidden = name !== "error";
}
