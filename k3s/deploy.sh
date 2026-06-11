#!/usr/bin/env bash
# deploy.sh — Deploy distributed-job-scheduler to a k8s/k3s cluster.
#
# Required env vars:
#   POSTGRES_PASSWORD   PostgreSQL password (db + DATABASE_URL)
#   JWT_SECRET_KEY      Backend JWT signing key
#   DJANGO_SECRET_KEY   Frontend Django SECRET_KEY
#
# Optional env vars:
#   DOCKERHUB_USER      Docker registry user  -> creates registry-secret if set
#   DOCKERHUB_TOKEN     Docker registry token/password
#   INGRESS_CLASS       Override ingressClassName (default: leave as-is = nginx)
#
# Usage:
#   POSTGRES_PASSWORD=xxx JWT_SECRET_KEY=yyy DJANGO_SECRET_KEY=zzz ./deploy.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log()  { echo "[INFO]  $*"; }
warn() { echo "[WARN]  $*" >&2; }
err()  { echo "[ERROR] $*" >&2; }

# ─── 0. Preflight ────────────────────────────────────────────────────────────

missing=0
for var in POSTGRES_PASSWORD JWT_SECRET_KEY DJANGO_SECRET_KEY; do
  if [[ -z "${!var:-}" ]]; then
    err "Missing required env var: $var"
    missing=1
  fi
done
[[ $missing -eq 0 ]] || exit 1

command -v kubectl  >/dev/null || { err "kubectl not found"; exit 1; }
command -v envsubst >/dev/null || { err "envsubst not found (install gettext)"; exit 1; }

kubectl cluster-info --request-timeout=5s >/dev/null || {
  err "kubectl cannot reach a cluster"
  exit 1
}
log "Cluster reachable, starting deployment..."

# Warn-only capability checks (do not block deploy) ----------------------------

if ! kubectl get deployment metrics-server -n kube-system &>/dev/null \
   && ! kubectl top nodes &>/dev/null; then
  warn "metrics-server not detected -> HPAs will show <unknown> CPU and won't scale."
  warn "  install: kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml"
fi

if ! kubectl get ingressclass nginx &>/dev/null; then
  warn "ingressClass 'nginx' not found. k3s ships Traefik by default."
  warn "  Either install ingress-nginx, or set INGRESS_CLASS=traefik and re-run."
fi

# ─── 1. Namespace ────────────────────────────────────────────────────────────
# grafana-ingress.yaml lives in 'monitoring' (created by kube-prometheus-stack).
# Create it if missing so the ingress apply doesn't fail.
kubectl get namespace monitoring &>/dev/null || kubectl create namespace monitoring

# ─── 2. Secrets ──────────────────────────────────────────────────────────────

# registry-secret: referenced by scheduler.yaml + worker.yaml (imagePullSecrets).
# Images are public on Docker Hub, so this is OPTIONAL — a missing pull secret
# only produces a warning event, not a failure. Create it only if creds given.
if [[ -n "${DOCKERHUB_USER:-}" && -n "${DOCKERHUB_TOKEN:-}" ]]; then
  log "Creating registry-secret from DOCKERHUB_* credentials..."
  kubectl create secret docker-registry registry-secret \
    --docker-server=https://index.docker.io/v1/ \
    --docker-username="$DOCKERHUB_USER" \
    --docker-password="$DOCKERHUB_TOKEN" \
    --dry-run=client -o yaml | kubectl apply -f -
else
  warn "registry-secret not created (no DOCKERHUB_USER/TOKEN). OK for public images."
fi

# frontend-secret: not defined in any manifest, create imperatively.
log "Creating frontend-secret..."
kubectl create secret generic frontend-secret \
  --from-literal=SECRET_KEY="$DJANGO_SECRET_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -

# ─── 3. Database (Secret + PVC + ConfigMap + Deployment + Service) ───────────
# db.yaml has ${POSTGRES_PASSWORD}/${JWT_SECRET_KEY} placeholders in the Secret.
# Restrict envsubst to ONLY those two vars so plpgsql '$$' dollar-quoting in the
# init SQL is left untouched.
log "Deploying database (job-scheduler-secret + db)..."
envsubst '${POSTGRES_PASSWORD} ${JWT_SECRET_KEY}' < "$SCRIPT_DIR/db.yaml" | kubectl apply -f -

log "Waiting for db rollout (readinessProbe: pg_isready)..."
kubectl rollout status deployment/db --timeout=180s

# ─── 4. Backend ──────────────────────────────────────────────────────────────
log "Deploying backend..."
kubectl apply -f "$SCRIPT_DIR/backend.yaml"
kubectl rollout status deployment/backend --timeout=120s

# ─── 5. Scheduler + Worker ───────────────────────────────────────────────────
# Same image as backend; run scheduler_loop / worker_loop, talk to db directly.
log "Deploying scheduler + worker..."
kubectl apply -f "$SCRIPT_DIR/scheduler.yaml"
kubectl rollout status deployment/scheduler --timeout=120s
kubectl rollout status deployment/worker --timeout=120s

# ─── 6. Frontend ─────────────────────────────────────────────────────────────
# Django + gunicorn; runs migrate on boot; calls http://backend:8000/api (in-cluster DNS).
log "Deploying frontend..."
kubectl apply -f "$SCRIPT_DIR/frontend.yaml"
kubectl rollout status deployment/frontend --timeout=120s

# ─── 7. Ingress ──────────────────────────────────────────────────────────────
# Optional ingressClass override (e.g. INGRESS_CLASS=traefik for default k3s).
apply_ingress() {
  local file="$1"
  if [[ -n "${INGRESS_CLASS:-}" ]]; then
    sed "s/ingressClassName: nginx/ingressClassName: ${INGRESS_CLASS}/" "$file" | kubectl apply -f -
  else
    kubectl apply -f "$file"
  fi
}
log "Applying app ingress (default ns)..."
apply_ingress "$SCRIPT_DIR/ingress.yaml"
log "Applying grafana ingress (monitoring ns)..."
apply_ingress "$SCRIPT_DIR/grafana-ingress.yaml"

# ─── 8. HPA ──────────────────────────────────────────────────────────────────
# CPU HPAs need metrics-server. worker-hpa also uses custom metric
# scheduler_queue_length -> needs Prometheus Adapter; without it that rule is
# simply ignored and worker scales on CPU only.
log "Applying HPAs..."
kubectl apply -f "$SCRIPT_DIR/hpa-backend.yaml"
kubectl apply -f "$SCRIPT_DIR/hpa-scheduler.yaml"
kubectl apply -f "$SCRIPT_DIR/hpa-worker.yaml"

# ─── 9. Summary ──────────────────────────────────────────────────────────────
echo ""
echo "=== Deployments ===";  kubectl get deployments -n default
echo "";  echo "=== Services ===";  kubectl get svc -n default
echo "";  echo "=== Ingress ===";   kubectl get ingress -A
echo "";  echo "=== HPA ===";       kubectl get hpa -n default

NODE_IP="$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')"
echo ""
echo "=== NodePort access ==="
echo "  Backend docs : http://${NODE_IP}:30080/api/docs"
echo "  Frontend     : http://${NODE_IP}:30081"
echo ""
log "Deploy complete."
