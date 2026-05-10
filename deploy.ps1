# ═══════════════════════════════════════════════════════════════════════════════
#  deploy.ps1  —  Deploy AI Creative Studio to Google Cloud Run
#
#  Prerequisites:
#    1. Install Google Cloud SDK: https://cloud.google.com/sdk/docs/install
#    2. Run: gcloud auth login
#    3. Run: gcloud config set project YOUR_PROJECT_ID
#
#  Usage:
#    .\deploy.ps1                         # use current gcloud project
#    .\deploy.ps1 -ProjectId my-proj      # explicit project
#    .\deploy.ps1 -Region europe-west1    # deploy to a different region
# ═══════════════════════════════════════════════════════════════════════════════
param(
    [string]$ProjectId = "",
    [string]$Region    = "us-central1",
    [string]$Service   = "ai-creative-studio"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Step([string]$msg) { Write-Host "`n▶  $msg" -ForegroundColor Cyan }
function OK  ([string]$msg) { Write-Host "   ✓  $msg" -ForegroundColor Green }
function Warn([string]$msg) { Write-Host "   !  $msg" -ForegroundColor Yellow }
function Die ([string]$msg) { Write-Host "`n✗  $msg" -ForegroundColor Red; exit 1 }

# ── Sanity checks ──────────────────────────────────────────────────────────────
Step "Checking prerequisites"
if (-not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
    Die "gcloud not found. Install Google Cloud SDK: https://cloud.google.com/sdk/docs/install"
}
OK "gcloud found"

# ── Resolve project ────────────────────────────────────────────────────────────
if (-not $ProjectId) {
    $ProjectId = (gcloud config get-value project 2>$null).Trim()
}
if (-not $ProjectId -or $ProjectId -eq "(unset)") {
    Die "No GCP project set.  Run: gcloud config set project YOUR_PROJECT_ID"
}

$Image  = "gcr.io/$ProjectId/$Service"
$Bucket = "$($ProjectId)-aics-outputs"

Write-Host @"

  Project  : $ProjectId
  Region   : $Region
  Service  : $Service
  Image    : $Image
  Bucket   : gs://$Bucket
"@ -ForegroundColor White

# ── Enable required APIs ───────────────────────────────────────────────────────
Step "Enabling required GCP APIs"
gcloud services enable `
    cloudbuild.googleapis.com `
    run.googleapis.com `
    containerregistry.googleapis.com `
    storage.googleapis.com `
    --project $ProjectId --quiet
OK "APIs enabled"

# ── Cloud Storage bucket for persistent outputs ────────────────────────────────
Step "Setting up Cloud Storage bucket for generated outputs"
$exists = gsutil ls "gs://$Bucket" 2>$null
if ($LASTEXITCODE -ne 0) {
    gsutil mb -p $ProjectId -l $Region "gs://$Bucket"
    OK "Created bucket gs://$Bucket"
} else {
    OK "Bucket already exists"
}

# Grant the default Compute SA (used by Cloud Run) read/write access to the bucket
$ProjectNumber = (gcloud projects describe $ProjectId --format "value(projectNumber)" 2>$null).Trim()
$SA = "$ProjectNumber-compute@developer.gserviceaccount.com"
gsutil iam ch "serviceAccount:${SA}:roles/storage.objectAdmin" "gs://$Bucket" 2>$null
OK "Service account $SA → storage.objectAdmin on bucket"

# ── Build image with Cloud Build ───────────────────────────────────────────────
Step "Building Docker image with Cloud Build"
Write-Host "   (first build takes ~5-8 min; subsequent builds are faster)" -ForegroundColor Gray

gcloud builds submit `
    --tag           $Image `
    --project       $ProjectId `
    --timeout       1800 `
    .
OK "Image built and pushed → $Image"

# ── Deploy to Cloud Run ────────────────────────────────────────────────────────
Step "Deploying to Cloud Run"
gcloud run deploy $Service `
    --image               $Image `
    --region              $Region `
    --platform            managed `
    --allow-unauthenticated `
    --memory              4Gi `
    --cpu                 2 `
    --concurrency         5 `
    --timeout             900 `
    --min-instances       0 `
    --max-instances       3 `
    --add-volume          "name=outputs,type=cloud-storage,bucket=$Bucket" `
    --add-volume-mount    "volume=outputs,mount-path=/app/backend/outputs" `
    --project             $ProjectId `
    --quiet

$Url = (gcloud run services describe $Service `
    --region  $Region `
    --format  "value(status.url)" `
    --project $ProjectId 2>$null).Trim()

Write-Host @"

╔══════════════════════════════════════════════════════╗
║  Deployment complete!                                ║
╚══════════════════════════════════════════════════════╝

  URL      →  $Url
  Outputs  →  gs://$Bucket  (persistent across deploys)

  To redeploy after code changes, just run this script again.
  To view logs: gcloud run services logs read $Service --region $Region
"@ -ForegroundColor Green
