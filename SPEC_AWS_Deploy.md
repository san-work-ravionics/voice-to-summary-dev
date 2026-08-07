# SPEC — AWS Production Deployment

**Created:** 2026-08-07
**Status:** Planning complete, implementation not started
**Target:** End-of-August 2026 demo
**Domain:** `voice.ravionics.nl`

---

## Architecture — RITA as Gateway

RITA EC2's nginx does hostname-based routing. `voice.ravionics.nl` proxies to a second t3.micro in the same VPC. Single Elastic IP, Cloudflare terminates TLS.

```
              Cloudflare (TLS, DNS)
                   |
         *.ravionics.nl → EIP (existing, 13.206.230.76)
                   |
        [ t3.micro A — RITA + Gateway ]
         nginx :80  (hostname routing)
           |
           +— riia.ravionics.nl  → localhost:8000  (RITA container)
           +— voice.ravionics.nl → 10.0.1.X:8743   (VtS on micro B)
                                         |
                                [ t3.micro B — VtS ]
                                 Docker → :8743
                                 (same VPC, public subnet, no EIP)
```

**Cost: ~$11.26/mo** (RITA micro free-tier, VtS micro $7.59, EIP $3.67).

**Future upgrade path:** If the project continues past the Aug demo, extract nginx into its own t3.micro gateway (~$19/mo total). Each app becomes fully independent.

---

## Decision Log

| Decision | Choice | Why |
|---|---|---|
| Architecture | RITA-as-gateway | Cheapest ($11/mo); ALB ($18+) overkill since Cloudflare handles TLS/caching |
| Instance type | t3.micro | Webapp at rest uses ~50-80 MB; Whisper burst ~200 MB fits with swap |
| LLM provider online | Claude API (Haiku) | Local models (Qwen/Mistral) need 2-6 GB RAM — won't fit on micro |
| Retrieval options | Both TF-IDF and FAISS shown | FAISS may OOM on micro — show friendly error, suggest TF-IDF |
| Local provider UI | Visible but amber-colored with timing estimates | User decision: don't hide options, show expected processing time |
| Auth | Google OAuth (same as RITA) | Consistent auth pattern across ravionics.nl apps |
| Elastic IP | Yes (shared with RITA) | Needed for Cloudflare A-record stability |
| Pipeline buttons (Scenarios) | Left as-is | Will fail on micro; acceptable — not the online use case |
| Whisper model | Bake into Docker image | Avoid cold-start download on first voice query |

---

## Implementation Phases

### Phase 1: Voice Query UI — provider hints + FAISS error handling
**Status:** Done
**Files:** `webapp/app.js`, `webapp/style.css`, `webapp/server.py`

- [x] Provider dropdown: Local/Mistral options shown in amber/muted color
- [x] Provider timing hints: show estimated processing time when provider is selected
  - Claude: "~15-30s (transcribe ~10s + retrieve <1s + API answer ~5s)"
  - Local Qwen: "~3-5 min (transcribe ~10s + model load ~2 min + generate ~1 min)"
  - Local Mistral: "~5-10 min (transcribe ~10s + model load ~3 min + generate ~2 min)"
- [x] FAISS OOM handling: if subprocess exits with SIGKILL (-9) or MemoryError, show:
  "FAISS retrieval ran out of memory on this server. Try again with TF-IDF retrieval."
- [x] `server.py`: detect OOM in `_start_voice_query` waiter (returncode -9, stderr MemoryError)

### Phase 2: Dockerfile optimization
**Status:** Done (code change applied; local Docker test deferred to user)
**Files:** `Dockerfile`

- [x] Bake Whisper base model into the image:
  `RUN python -c "import whisper; whisper.load_model('base')"`
- [x] Verify CPU-only torch is already configured (it is — no change needed)
- [ ] Test locally: `docker compose build && docker compose up`, verify voice query works

### Phase 3: Google OAuth
**Status:** Done (code complete; Google Cloud Console registration + secrets deferred to deploy time)
**Files:** `webapp/server.py`, `webapp/app.js`, `docker-compose.yml`

- [x] Add `/auth/login`, `/auth/callback`, `/auth/check`, `/api/auth/enabled` endpoints to `server.py`
- [x] Add JWT token creation/verification (stdlib only — hmac+hashlib, no jose dependency)
- [x] Gate all `/api/*` endpoints behind auth check when `VTS_AUTH=google`
- [x] Auth disabled when `VTS_AUTH` is unset (local dev — no login required)
- [x] `app.js`: check auth on startup, auto-inject Bearer token on API fetches, redirect to login if needed
- [x] Callback page stores JWT in localStorage as `vts_token` and redirects to app
- [x] `docker-compose.yml`: added `VTS_AUTH`, `VTS_JWT_SECRET`, `VTS_BASE_URL`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` env vars
- [ ] Google Cloud Console: register `http://voice.ravionics.nl/auth/callback` (at deploy time)
- [ ] Set GitHub Secrets: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `VTS_JWT_SECRET`, `VTS_BASE_URL`

### Phase 4: Terraform — second EC2 instance
**Status:** Code complete (apply deferred to deploy time)
**Files:** `terraform/main.tf`, `terraform/variables.tf`, `terraform/providers.tf`, `terraform/outputs.tf`
**Reference:** `riia-aug-release/terraform/main.tf` (pattern only — do not modify RIIA files)

- [x] Create `terraform/` directory in this project
- [x] `providers.tf` — AWS provider, ap-south-1, terraform >= 1.6
- [x] `variables.tf` — instance_type (default t3.micro), alert_email, etc.
- [x] `main.tf` — VPC data source (reference RITA's existing VPC/subnet), plus:
  - `aws_instance.vts` — Ubuntu 22.04, t3.micro, 30 GB gp3, same subnet as RITA
  - user_data: install Docker, create `/opt/vts/` directories, add 2 GB swap
  - `aws_security_group.vts` — ingress 8743 from RITA SG only, SSH from anywhere
  - `aws_cloudwatch_log_group.vts` — `/vts/app`, 30-day retention
  - SSH key pair (own, not RITA's)
  - No EIP for VtS
- [x] `outputs.tf` — VtS private IP (needed for nginx config on RITA)
- [ ] Run `terraform apply`
- [ ] SSH in, verify Docker installed, swap active, directories created

### Phase 5: nginx multi-host routing + Cloudflare DNS
**Status:** nginx config written (apply + Cloudflare DNS deferred to deploy time)
**Files:** `terraform/rita-nginx-update.conf` (reference config, applied manually to RITA EC2)
**Reference:** `riia-aug-release/terraform/rita.nginx.conf`

- [x] Write the updated nginx config in this project as a reference file
- [ ] Apply to RITA EC2 manually (SSH in, update `/etc/nginx/sites-available/default`, reload)
  - `riia.ravionics.nl` → localhost:8000 (keep existing RITA config including MCP SSE)
  - `voice.ravionics.nl` → VtS private IP:8743
  - Default `server_name _` → return 444
- [ ] Cloudflare: add A record `voice.ravionics.nl` → existing EIP (13.206.230.76)
- [ ] Enable orange cloud proxy
- [ ] Verify: `curl -H "Host: voice.ravionics.nl" http://13.206.230.76/healthz`

### Phase 6: CI/CD — GitHub Actions deploy pipeline
**Status:** Pipeline written (secrets + first deploy deferred)
**Files:** `.github/workflows/deploy.yaml`

- [ ] Create GitHub repo for voice-to-summary (or push to existing)
- [x] Write deploy.yaml (two-job: build-and-push → deploy)
- [x] deploy job: rsync phase outputs + audio to `/opt/vts/`, pull image, `docker run`
- [x] `docker run` flags: port 8743, memory 900m, awslogs driver, volume mounts
- [ ] Set GitHub Secrets: `SSH_PRIVATE_KEY`, `VTS_EC2_IP`, `GHCR_PAT`, `ANTHROPIC_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `VTS_JWT_SECRET`, `VTS_BASE_URL`
- [ ] Push to trigger first deploy
- [ ] Verify health: `curl https://voice.ravionics.nl/healthz`
- [ ] Verify CloudWatch log group `/vts/app` populates
- [ ] End-to-end: voice query with Claude + TF-IDF on `voice.ravionics.nl`

---

## Volume Mounts (EC2 → Container)

```
/opt/vts/audio/output       → /app/audio-generation/output
/opt/vts/phase1/output      → /app/phase1-baseline/output
/opt/vts/phase2/output      → /app/phase2-checklist/output
/opt/vts/phase3/output      → /app/phase3-context/output
/opt/vts/phase4/output      → /app/phase4-assistant/output
/opt/vts/phase5/output      → /app/phase5-office-agent/output
/opt/vts/phase6/output      → /app/phase6-history/output
/opt/vts/phase7/output      → /app/phase7-reference-rag/output
/opt/vts/phase8/output      → /app/phase8-voice-query/output
/opt/vts/eval/output        → /app/eval/output
/opt/vts/logs               → /app/logs
/opt/vts/run_status         → /app/webapp/.run_status
/opt/vts/cache              → /cache            (named volume for Whisper/HF models)
```

---

## GitHub Secrets

| Secret | Used for |
|---|---|
| `SSH_PRIVATE_KEY` | SSH into VtS EC2 for deploy |
| `VTS_EC2_IP` | VtS instance public IP (for SSH; not user-facing) |
| `GHCR_PAT` | Pull private Docker images from GHCR (reuse RIIA's PAT) |
| `ANTHROPIC_API_KEY` | Claude API for voice query answering |
| `GOOGLE_CLIENT_ID` | Google OAuth login |
| `GOOGLE_CLIENT_SECRET` | Google OAuth login |
| `VTS_JWT_SECRET` | JWT signing key (min 32 chars) |
| `VTS_BASE_URL` | `http://voice.ravionics.nl` (OAuth callback base) |

---

## docker run (production)

```bash
docker run -d --name vts --restart unless-stopped \
  -p 8743:8743 \
  -e SUMMARY_PROVIDER=claude \
  -e ANTHROPIC_API_KEY='...' \
  -e GOOGLE_CLIENT_ID='...' \
  -e GOOGLE_CLIENT_SECRET='...' \
  -e VTS_JWT_SECRET='...' \
  -e VTS_BASE_URL='http://voice.ravionics.nl' \
  -v /opt/vts/audio/output:/app/audio-generation/output:ro \
  -v /opt/vts/phase1/output:/app/phase1-baseline/output:ro \
  -v /opt/vts/phase2/output:/app/phase2-checklist/output:ro \
  -v /opt/vts/phase3/output:/app/phase3-context/output:ro \
  -v /opt/vts/phase4/output:/app/phase4-assistant/output:ro \
  -v /opt/vts/phase5/output:/app/phase5-office-agent/output:ro \
  -v /opt/vts/phase6/output:/app/phase6-history/output:ro \
  -v /opt/vts/phase7/output:/app/phase7-reference-rag/output:ro \
  -v /opt/vts/phase8/output:/app/phase8-voice-query/output \
  -v /opt/vts/eval/output:/app/eval/output:ro \
  -v /opt/vts/logs:/app/logs \
  -v /opt/vts/run_status:/app/webapp/.run_status \
  -v vts_cache:/cache \
  --memory 900m \
  --log-driver awslogs \
  --log-opt awslogs-region=ap-south-1 \
  --log-opt awslogs-group=/vts/app \
  --log-opt awslogs-stream=vts-container \
  ghcr.io/<repo>/vts:latest
```

---

## EC2 Setup Checklist (first boot)

```bash
ssh -i terraform/generated-key.pem ubuntu@<VTS_EC2_IP>

# 1. Add 2 GB swap
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# 2. Create data directories
sudo mkdir -p /opt/vts/{audio/output,phase1/output,phase2/output,phase3/output,phase4/output,phase5/output,phase6/output,phase7/output,phase8/output,eval/output,logs,run_status,cache}
sudo chown -R ubuntu:ubuntu /opt/vts

# 3. Verify Docker installed (should be via user_data)
docker --version

# 4. Attach IAM role for CloudWatch (via AWS Console)
# EC2 → Instance → Actions → Security → Modify IAM role → rita-ec2-role
```

---

## RIIA Reference Files

| What | Path |
|---|---|
| Terraform config | `riia-jun-release/terraform/main.tf` |
| nginx config | `riia-jun-release/terraform/rita.nginx.conf` |
| CI/CD pipeline | `riia-aug-release/.github/workflows/deploy.yaml` |
| Deploy spec | `riia-agentic-firm/project-office/specs/SPEC_Prod_Deploy.md` |
| Deploy knowledge base | `riia-agentic-firm/project-office/ops-deployments/DEPLOYMENT_KNOWLEDGE.md` |
