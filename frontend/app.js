const form = document.getElementById("generate-form");
const submitBtn = document.getElementById("submit-btn");
const submitStatus = document.getElementById("submit-status");
const jobsList = document.getElementById("jobs-list");
const refreshBtn = document.getElementById("refresh-btn");

const modal = document.getElementById("result-modal");
const modalTitle = document.getElementById("modal-title");
const modalPrompt = document.getElementById("modal-prompt");
const modalImage = document.getElementById("modal-image");
const modalReferenceWrap = document.getElementById("modal-reference-wrap");
const modalReferenceImage = document.getElementById("modal-reference-image");
document.getElementById("modal-close").onclick = () => modal.classList.add("hidden");

// jobs still in flight get polled every couple seconds so the badge
// updates itself without the user having to hit refresh manually
const pollingJobs = new Set();

async function fetchJobs() {
  const res = await fetch("/jobs");
  const jobs = await res.json();
  renderJobs(jobs);

  jobs.forEach((job) => {
    if (job.status === "pending" || job.status === "processing") {
      pollJob(job.id);
    }
  });
}

function pollJob(jobId) {
  if (pollingJobs.has(jobId)) return;
  pollingJobs.add(jobId);

  const interval = setInterval(async () => {
    const res = await fetch(`/jobs/${jobId}`);
    if (!res.ok) {
      clearInterval(interval);
      pollingJobs.delete(jobId);
      return;
    }
    const job = await res.json();
    updateJobCard(job);

    if (job.status === "completed" || job.status === "failed") {
      clearInterval(interval);
      pollingJobs.delete(jobId);
    }
  }, 2000);
}

function renderJobs(jobs) {
  if (jobs.length === 0) {
    jobsList.innerHTML = `<p class="empty-state">No jobs yet - submit a product above to kick one off.</p>`;
    return;
  }
  jobsList.innerHTML = "";
  jobs.forEach((job) => jobsList.appendChild(buildJobCard(job)));
}

function buildJobCard(job) {
  const card = document.createElement("div");
  card.className = "job-card";
  card.dataset.jobId = job.id;
  card.innerHTML = jobCardHTML(job);

  const viewBtn = card.querySelector(".view-btn");
  if (viewBtn) {
    viewBtn.onclick = () => openModal(job);
  }
  return card;
}

function jobCardHTML(job) {
  const canView = job.status === "completed";
  return `
    <div class="job-info">
      <span class="job-name">${escapeHtml(job.product_name)}</span>
      <span class="job-desc">${escapeHtml(job.description)}</span>
    </div>
    <div class="job-actions" style="display:flex; align-items:center; gap:10px;">
      <span class="badge ${job.status}">${job.status}</span>
      <button class="view-btn" ${canView ? "" : "disabled"}>View</button>
    </div>
  `;
}

function updateJobCard(job) {
  const card = jobsList.querySelector(`[data-job-id="${job.id}"]`);
  if (!card) return;
  card.innerHTML = jobCardHTML(job);
  const viewBtn = card.querySelector(".view-btn");
  if (viewBtn) viewBtn.onclick = () => openModal(job);
}

function openModal(job) {
  modalTitle.textContent = job.product_name;
  modalPrompt.textContent = job.generated_prompt || "";
  modalImage.src = job.result_image_url || "";

  if (job.reference_image_url) {
    modalReferenceImage.src = job.reference_image_url;
    modalReferenceWrap.classList.remove("hidden");
  } else {
    modalReferenceWrap.classList.add("hidden");
  }

  modal.classList.remove("hidden");
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  submitBtn.disabled = true;
  submitStatus.textContent = "Submitting...";

  const productNameInput = document.getElementById("product_name");
  const descriptionInput = document.getElementById("description");
  const imageInput = document.getElementById("product_image");

  const formData = new FormData();
  formData.append("product_name", productNameInput.value.trim());
  formData.append("description", descriptionInput.value.trim());
  if (imageInput.files[0]) {
    formData.append("product_image", imageInput.files[0]);
  }

  try {
    // no Content-Type header here on purpose - the browser sets the
    // multipart boundary itself when the body is a FormData instance
    const res = await fetch("/generate", {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json();
      submitStatus.textContent = err.error || "Something went wrong.";
      return;
    }

    const job = await res.json();
    submitStatus.textContent = "Job queued.";
    form.reset();
    await fetchJobs();
    pollJob(job.id);
  } catch (err) {
    submitStatus.textContent = "Network error - is the backend running?";
  } finally {
    submitBtn.disabled = false;
  }
});

refreshBtn.addEventListener("click", fetchJobs);

fetchJobs();
