# Step 6: Kubernetes

The app and its monitoring now run on a Kubernetes cluster, deployed with two commands.

## Prerequisites

| Need | How |
|------|-----|
| A cluster | Docker Desktop: Settings → Kubernetes → Enable Kubernetes |
| `kubectl` | Comes with Docker Desktop |

Check: `kubectl get nodes` should list nodes with status `Ready`.

## Deploy

```bash
# 1. Build the image the cluster will run
docker build -t rag-pdf:1.0 .

# 2. Put your Gemini key where Kubernetes will read it (file is not in git)
grep '^GEMINI_API_KEY=' .env > k8s/secret.env

# 3. Deploy the app
kubectl apply -k k8s/

# 4. Deploy monitoring (optional)
kubectl apply -k monitoring/

# 5. Wait until everything is Running
kubectl -n rag-pdf get pods
```

## Open it

Services are only reachable inside the cluster. `port-forward` connects one to your machine for as long as the command runs:

```bash
kubectl -n rag-pdf port-forward svc/app 8000:8000        # http://localhost:8000
kubectl -n rag-pdf port-forward svc/grafana 3000:3000    # http://localhost:3000  admin / admin
```

Run each in its own terminal.

## What gets created

Everything lives in the `rag-pdf` namespace.

```
              ┌── ConfigMap app-config   (settings)
Deployment ───┼── Secret    app-secret   (GEMINI_API_KEY)
   app        └── PVC       app-data     (vector database)
    ▲
    │
Service app  ◄── port-forward ◄── your browser
```

### App (`k8s/`)

| File | Kind | Purpose |
|------|------|---------|
| `namespace.yaml` | Namespace | Groups everything, separate from the rest of the cluster |
| `config.env` | ConfigMap `app-config` | Non-secret settings, as environment variables |
| `secret.env` | Secret `app-secret` | `GEMINI_API_KEY`. Not in git; `secret.env.example` is the template |
| `pvc.yaml` | PersistentVolumeClaim `app-data` | 1 GB disk for ChromaDB, mounted at `/data` |
| `deployment.yaml` | Deployment `app` | Runs the container and keeps it running |
| `service.yaml` | Service `app` | Stable address `http://app:8000` inside the cluster |
| `kustomization.yaml` | | Ties the files together; sets namespace and image tag |

### Monitoring (`monitoring/`)

| File | Creates |
|------|---------|
| `k8s/prometheus.yaml` | Prometheus Deployment, Service, 2 GB disk |
| `k8s/loki.yaml` | Loki Deployment, Service, 2 GB disk |
| `k8s/alloy.yaml` | Alloy Deployment, plus read-only permission to read pod logs in this namespace |
| `k8s/grafana.yaml` | Grafana Deployment and Service |
| `alloy-k8s.alloy` | Alloy's config for Kubernetes |
| `kustomization.yaml` | Turns the config files into ConfigMaps |

`prometheus.yml`, the Grafana datasources and the dashboard are the same files Docker Compose uses. That works because the Kubernetes Services have the same names as the Compose services (`app`, `loki`, `prometheus`).

## How it maps from Docker Compose

| Docker Compose | Kubernetes |
|----------------|------------|
| `services: app` | Deployment + Service |
| `env_file: .env` | ConfigMap + Secret |
| `volumes: rag_data` | PersistentVolumeClaim |
| `ports: "8000:8000"` | Service + `port-forward` |
| `restart: unless-stopped` | Built in: a Deployment always replaces a dead pod |
| `HEALTHCHECK` | Startup, readiness and liveness probes |
| `--profile monitoring` | A separate `kubectl apply -k monitoring/` |

## The Deployment, explained

| Setting | Value | Why |
|---------|-------|-----|
| `replicas` | `1` | ChromaDB is a database on the pod's disk. A second pod would have its own separate documents |
| `strategy` | `Recreate` | Stop the old pod before starting the new one; both cannot use the disk at once. Costs a few seconds of downtime per update |
| `envFrom` | ConfigMap + Secret | Every key becomes an environment variable, which is what `config.py` reads |
| `resources.requests` | 250m CPU, 768 MB | Reserved for the pod. The app uses about 450 MB idle |
| `resources.limits` | 2 GB memory | The pod is restarted if it exceeds this |
| `securityContext` | Non-root user 1000, no privilege escalation | Limits what a bug in the app could do |
| `startupProbe` | `/health`, up to 2.5 minutes | Gives the embedding model time to load |
| `readinessProbe` | `/health` every 10 s | Traffic is only sent while the app answers |
| `livenessProbe` | `/health` every 20 s | The container is restarted after 3 failures in a row |

## Kustomize

`kubectl apply -k <folder>` reads `kustomization.yaml` in that folder. It is built into `kubectl`; nothing to install. Here it does three jobs:

| Job | Effect |
|-----|--------|
| `namespace: rag-pdf` | Puts every resource in the namespace |
| `images:` | Sets the real image name and tag in one place |
| `configMapGenerator` / `secretGenerator` | Builds the ConfigMap and Secret from `.env`-style files |

Generated ConfigMaps and Secrets get a hash in their name, like `app-config-72hk4gh4hf`. When a value changes, the name changes, so the Deployment restarts by itself and picks it up.

To see the final YAML without applying it: `kubectl kustomize k8s/`

## Everyday commands

All need `-n rag-pdf`.

| Command | Does |
|---------|------|
| `kubectl -n rag-pdf get pods` | Status of every pod |
| `kubectl -n rag-pdf logs -f deploy/app` | Follow the app's logs |
| `kubectl -n rag-pdf describe pod -l app=app` | Why a pod is not starting (see Events at the bottom) |
| `kubectl -n rag-pdf rollout restart deploy/app` | Restart the app |
| `kubectl -n rag-pdf rollout status deploy/app` | Wait for an update to finish |
| `kubectl -n rag-pdf exec -it deploy/app -- sh` | Open a shell in the container |
| `kubectl -n rag-pdf get all,pvc,cm,secret` | Everything that exists |

## Common changes

| Change | How |
|--------|-----|
| A setting | Edit `k8s/config.env`, then `kubectl apply -k k8s/` |
| The API key | Edit `k8s/secret.env`, then `kubectl apply -k k8s/` |
| The code | `docker build -t rag-pdf:1.1 .`, set `newTag: "1.1"` in `k8s/kustomization.yaml`, then `kubectl apply -k k8s/` |
| The dashboard | Edit `monitoring/grafana/dashboards/rag-pdf.json`, then `kubectl apply -k monitoring/` |

Use a new tag for each build. Rebuilding under the same tag does not update a running cluster.

## Remove

| Command | Removes |
|---------|---------|
| `kubectl delete -k monitoring/` | Monitoring, including its stored metrics and logs |
| `kubectl delete -k k8s/` | The app, **including all indexed documents** |

## Using a real cluster

Docker Desktop's cluster can use images built on your machine. A cloud cluster cannot, so the image must go to a registry:

```bash
docker build --platform linux/amd64 -t yourname/rag-pdf:1.0 .
docker push yourname/rag-pdf:1.0
```

Then in `k8s/kustomization.yaml` set `newName: yourname/rag-pdf`.

Also needed there, and not included here:

| Missing | Why it matters |
|---------|----------------|
| Ingress with HTTPS | A public URL instead of `port-forward` |
| Login for the app | Anyone who can reach it can upload, ask and delete |
| A real Grafana password | It is `admin` in `monitoring/k8s/grafana.yaml` |
| Backups of the `app-data` disk | Deleting the PVC deletes every indexed document |

## Limits

| Limit | Effect |
|-------|--------|
| One app replica | No scaling and no zero-downtime updates. Fixing this means running ChromaDB as its own server |
| Secrets are only base64-encoded in the cluster | Anyone with access to the namespace can read the key |
| Prometheus finds the app by its Service name | Fine for one replica; several would need per-pod discovery |
| Grafana has no disk | Changes made in the Grafana UI are lost on restart. Edit the dashboard file instead |
| Logs are kept forever | Loki has no retention configured; its 2 GB disk fills eventually |

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `connection refused` to `localhost:8080` | No cluster running | Enable Kubernetes in Docker Desktop |
| `unable to find file secret.env` | Step 2 skipped | `grep '^GEMINI_API_KEY=' .env > k8s/secret.env` |
| Pod `ErrImagePull` / `ImagePullBackOff` | Image `rag-pdf:1.0` does not exist | `docker build -t rag-pdf:1.0 .` |
| Pod `Pending` | No disk or not enough memory | `kubectl -n rag-pdf describe pod -l app=app` |
| Pod `CrashLoopBackOff` | The app fails at start | `kubectl -n rag-pdf logs deploy/app` |
| Pod `Running` but `0/1` ready | Still loading the model | Wait up to a minute |
| `namespaces "rag-pdf" not found` | Monitoring applied before the app | `kubectl apply -k k8s/` first |
| Browser cannot connect | `port-forward` is not running | Start it again |
