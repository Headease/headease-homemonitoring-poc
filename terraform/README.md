# Terraform Deployment

Deploys the HeadEase Home Monitoring PoC to Google Kubernetes Engine.

## What it creates

| Resource | Description |
|----------|-------------|
| GKE Cluster | Single-node `e2-standard-2` in `europe-west4` |
| Namespace | `headease-homemonitoring` |
| Helm Release | Deploys the `../helm/headease-homemonitoring` chart |

State is stored in a GCS bucket (`cumuluz-vws-hackathon-april-26-tf-state`).

## Prerequisites

- [Terraform](https://www.terraform.io/) >= 1.6.0
- `gcloud` CLI authenticated with the project
- Docker image pushed to Artifact Registry
- mTLS certificates available

### One-time setup

```bash
# Authenticate
gcloud auth application-default login
gcloud config set project cumuluz-vws-hackathon-april-26

# Enable required APIs
gcloud services enable container.googleapis.com artifactregistry.googleapis.com

# Create state bucket
gsutil mb -p cumuluz-vws-hackathon-april-26 -l europe-west4 gs://cumuluz-vws-hackathon-april-26-tf-state

# Create Artifact Registry repo for Docker images
gcloud artifacts repositories create headease \
  --repository-format=docker \
  --location=europe-west4
```

## Build and push the Docker image

```bash
# From project root
docker build -t europe-west4-docker.pkg.dev/cumuluz-vws-hackathon-april-26/headease/headease-homemonitoring:latest .

gcloud auth configure-docker europe-west4-docker.pkg.dev
docker push europe-west4-docker.pkg.dev/cumuluz-vws-hackathon-april-26/headease/headease-homemonitoring:latest
```

## Deploy

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars  # edit as needed

terraform init
terraform plan
terraform apply
```

## Create the certificate secret

After the cluster is created, upload the mTLS certificates:

```bash
# Get cluster credentials
gcloud container clusters get-credentials headease-homemonitoring --region europe-west4

# Create the secret in the app namespace
kubectl -n headease-homemonitoring create secret generic headease-homemonitoring-certs \
  --from-file=uzi.crt=../certificates/headease-certificates-proeftuin/headease-uzi-external-intermediate/headease-uzi.crt \
  --from-file=uzi-chain.crt=../certificates/headease-certificates-proeftuin/headease-uzi-external-intermediate/headease-uzi-chain.crt \
  --from-file=uzi-intermediate.cer=../certificates/gfmodules-test-uzi-external-intermediate.cer \
  --from-file=ldn.crt=../certificates/headease-certificates-proeftuin/headease-ldn-external-intermediate/headease-ldn.crt \
  --from-file=ldn-chain.crt=../certificates/headease-certificates-proeftuin/headease-ldn-external-intermediate/headease-ldn-chain.crt \
  --from-file=private.key=../certificates/headease_nvi_20260202_145627.key
```

Then restart the pod to pick up the secret:

```bash
kubectl -n headease-homemonitoring rollout restart deployment headease-homemonitoring-headease-homemonitoring
```

## Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `project` | `cumuluz-vws-hackathon-april-26` | GCP project ID |
| `region` | `europe-west4` | GCP region |
| `cluster_name` | `headease-homemonitoring` | GKE cluster name |
| `node_machine_type` | `e2-standard-2` | Node VM type |
| `namespace` | `headease-homemonitoring` | Kubernetes namespace |
| `image_repository` | `europe-west4-docker.pkg.dev/.../headease-homemonitoring` | Docker image |
| `image_tag` | `latest` | Image tag |
| `fhir_base_url` | `https://ngrok.headease.nl/fhir` | Public FHIR URL |
| `ura_number` | `90000315` | Organization URA |
| `organization_name` | `HeadEase` | Organization name |
| `cert_secret_name` | `headease-homemonitoring-certs` | K8s Secret with certs |

## GitHub Actions CI/CD

The `.github/workflows/deploy.yml` workflow automatically builds and deploys on push to `main`. It requires a `GCP_SA_KEY` secret in the GitHub repository.

### Create the service account

```bash
PROJECT=cumuluz-vws-hackathon-april-26

# Create service account
gcloud iam service-accounts create github-deploy \
  --display-name="GitHub Actions Deploy" \
  --project=$PROJECT

SA_EMAIL=github-deploy@${PROJECT}.iam.gserviceaccount.com

# Grant required roles
gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/container.admin"

gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/artifactregistry.writer"

gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding $PROJECT \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/iam.serviceAccountUser"

# Create and download key
gcloud iam service-accounts keys create github-deploy-key.json \
  --iam-account=$SA_EMAIL
```

### Add the secret to GitHub

1. Go to the GitHub repository **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `GCP_SA_KEY`
4. Value: paste the contents of `github-deploy-key.json`
5. Delete the local key file: `rm github-deploy-key.json`

### Required roles summary

| Role | Purpose |
|------|---------|
| `roles/container.admin` | Create/manage GKE cluster, deploy Helm charts |
| `roles/artifactregistry.writer` | Push Docker images |
| `roles/storage.admin` | Access Terraform state bucket |
| `roles/iam.serviceAccountUser` | Create resources as the service account |

## Tear down

```bash
terraform destroy
```
