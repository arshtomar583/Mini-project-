# AWS EC2 deployment: learn, start for a demo, stop afterward

## Current status

The app has a Docker build and an EC2 service configuration. It is not deployed to AWS yet. An AWS account, instance, and public HTTPS hostname have not been created. No AWS credentials are needed in the app or its GitHub repository.

## The simple picture

```text
Browser → HTTPS hostname → Caddy → FastAPI → temporary analysis worker
                              │      └─ serves the built React website
                         one EC2 instance
```

- **EC2 instance:** a Linux computer rented from AWS. You can start and stop it.
- **Docker image:** a packaged copy of our application and its dependencies.
- **Container:** a running copy of that image. It reads uploaded Python without running that source.
- **Caddy:** the small web server in front of the app that supplies HTTPS when a real hostname is configured.
- **DNS:** connects a name such as `codebase.example.com` to the server's public IP address.

The website and API share an address. We do not need a separate frontend host, a database, or an LLM key for this release.

## 1. Create your account first

Create an account through [AWS Free Tier](https://aws.amazon.com/free/), choose the Free plan if offered, and complete identity, payment-method, and agreement steps yourself. Keep credentials and verification codes private. Turn on MFA for the account.

As checked on 10 November 2026, new accounts can receive $100 initially and earn up to $100 more. The Free plan ends after six months or when credits run out, whichever comes first; AWS says it does not charge until you convert to a Paid plan. Confirm the actual offer and remaining credits in your own account. Older tutorials describing twelve months of free EC2 may apply to an older account policy.

Before launching, review Billing / Free Tier and configure a budget notification. A budget alert is a notification, not a guaranteed spending cutoff. Do not switch to a Paid plan just to follow an outdated tutorial.

## 2. Choose a small server together

Proposed starting configuration (verify availability and estimated credit use in your account):

| Setting | Choice and reason |
| --- | --- |
| Name | `explain-this-codebase` |
| Region | One nearby region, such as Mumbai if available; keep resources in that region |
| Operating system | Official Canonical Ubuntu Server 24.04 LTS, x86_64 |
| Instance | A credit-eligible small x86 instance with at least 1 GiB RAM; confirm the console's estimate before launch |
| Root disk | Encrypted gp3, about 12 GiB initially; enough for Linux and Docker, monitor space |
| Public IPv4 | Auto-assign for initial SSH access; do not allocate an Elastic IP initially |
| Key pair | Create/download your own SSH key and store it privately; never commit it |
| IAM role | None required: this app does not call AWS APIs |
| Metadata | Require IMDSv2; keep hop limit 1 |
| SSH inbound | TCP 22 from **My IP**, not the whole internet |
| Web inbound | Keep closed during initial verification; add TCP 80/443 when publishing HTTPS |

Do not create a load balancer, NAT gateway, database, or paid DNS zone for this first deployment. A small instance can be slow during image builds; do not silently resize it to a paid option if a build fails. We will inspect logs and choose a build strategy first.

**What stopping does:** EC2 compute billing stops once the instance is stopped, but retained EBS storage still exists and can consume credits or incur charges under a paid account. The site is offline while stopped. An auto-assigned public IPv4 address is usually replaced on the next start, so update the DNS record and SSH destination. An Elastic IP keeps an address stable but is not a free way to avoid that update. Public IPv4 pricing is listed separately by AWS. See [EC2 stop/start](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Stop_Start.html) and [VPC public IPv4 pricing](https://aws.amazon.com/vpc/pricing/).

This makes start/stop suitable for scheduled demonstrations. A resume link will be unavailable while the server is stopped; retain a short demo recording and screenshots for that case.

## 3. Install and verify privately first

After launch, connect from PowerShell using your actual private-key path and current public IP. The `ubuntu` username applies to the proposed Ubuntu image:

```powershell
ssh -i "C:\path\to\your-key.pem" ubuntu@YOUR_EC2_PUBLIC_IP
```

On the instance, install Git and Docker Engine with the Compose plugin using [Docker's official Ubuntu instructions](https://docs.docker.com/engine/install/ubuntu/#install-using-the-repository). Use the package-repository method. Then verify:

```bash
sudo systemctl enable --now docker
sudo docker version
sudo docker compose version
git --version
```

Still on EC2:

```bash
git clone https://github.com/arshtomar583/Mini-project-.git explain-this-codebase
cd explain-this-codebase
sudo docker compose -f deploy/aws/compose.yaml config --quiet
sudo docker compose -f deploy/aws/compose.yaml up -d --build app
sudo docker compose -f deploy/aws/compose.yaml ps
python3 scripts/smoke_deployment.py http://127.0.0.1:10000 --wait-seconds 30 --github
```

The initial configuration exposes port 10000 only on the server's loopback interface. To see it from your own Windows browser, keep this second PowerShell window open:

```powershell
ssh -i "C:\path\to\your-key.pem" -N -L 10001:127.0.0.1:10000 ubuntu@YOUR_EC2_PUBLIC_IP
```

Open **http://127.0.0.1:10001/** locally. SSH encrypts that connection to EC2. This is a private deployment check, not the public website URL. Do not open port 10000 in the EC2 security group.

The smoke checker verifies health, the compiled website and assets, correct API errors, a real ZIP analysis, and optionally the public AltF4 download. It does not execute the uploaded sample. Also click through the graph in the browser before publishing.

## 4. Add the public HTTPS address

Choose a domain or a free DNS hostname you control; a purchased domain is optional. The setup below expects that hostname's A record to point to the current EC2 public IPv4 address. Avoid an AAAA record unless IPv6 is also configured and reachable. We will select the hostname provider together after the server works.

On EC2, from the repository root:

```bash
cp deploy/aws/.env.example deploy/aws/.env
nano deploy/aws/.env
```

Replace the example with `APP_DOMAIN=your-real-hostname` (no `https://` and no trailing slash). The `.env` file is ignored by Git. Then allow TCP 80 and 443 in the EC2 security group for public visitors, retaining SSH access only from your IP. This is the step that makes the service public.

```bash
sudo docker compose --env-file deploy/aws/.env -f deploy/aws/compose.yaml --profile public config --quiet
sudo docker compose --env-file deploy/aws/.env -f deploy/aws/compose.yaml --profile public up -d
sudo docker compose --env-file deploy/aws/.env -f deploy/aws/compose.yaml logs --tail=50 https
python3 scripts/smoke_deployment.py https://your-real-hostname --github
```

Caddy obtains/renews the certificate and redirects HTTP to HTTPS when DNS and incoming ports are correct. Its certificate data lives in named Docker volumes. Do not use a placeholder hostname or `localhost` as a public address. Do not bypass a certificate warning; correct DNS/firewall/certificate configuration instead. Reference: [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https).

## 5. Your start/stop routine

After a demo, use **EC2 → Instances → select this instance → Instance state → Stop instance**. Wait until AWS shows **Stopped**. Stopping only Docker does not stop EC2 compute use. Do not choose **Terminate** for an instance you intend to reuse.

Before a demo:

1. Start the same EC2 instance and wait for its status checks.
2. Read its current public IP. Update the hostname's DNS A record if it changed and allow DNS caches to expire.
3. Connect by SSH using that IP; update the SSH security-group source if your own IP changed.
4. Docker starts with the OS. Containers configured with `restart: unless-stopped` restart unless you explicitly stopped them with Docker previously.
5. Check `docker compose ps`, the health endpoint, and the smoke checker before sharing the link. If you used Compose `down`, run the appropriate `up -d` command again.

An expired HTTPS certificate may need renewal after a long shutdown. Keep DNS and ports 80/443 correct and wait for successful certificate issuance; don't promise an immediately working link after every restart.

## 6. Updating and troubleshooting

Once a reviewed commit passes GitHub Actions, SSH into the instance and run:

```bash
cd ~/explain-this-codebase
git pull --ff-only
sudo docker compose --env-file deploy/aws/.env -f deploy/aws/compose.yaml --profile public up -d --build
sudo docker compose --env-file deploy/aws/.env -f deploy/aws/compose.yaml --profile public ps
sudo docker compose --env-file deploy/aws/.env -f deploy/aws/compose.yaml --profile public logs --tail=50
```

Use the app-only command from step 3 until a public hostname is configured. Updating the image can cause a short interruption on this single server. Record the previous Git commit if rollback is needed. Logs are rotated to prevent unbounded disk use. The build cache and old images still use disk; check `sudo docker system df` before deciding what to remove.

The application admits one analysis at a time and at most 20 attempts per minute across all visitors. A 503 means busy; a 429 means wait for the stated retry time. The existing archive, extraction, worker-time, and report limits remain. This is a small demo service, not a high-traffic or denial-of-service-resistant deployment.

The app container has a 512 MiB memory cap, a process limit, a read-only filesystem, and a 64 MiB temporary filesystem. The analysis worker additionally has a 256 MiB address-space cap on Linux. Temporary source files are removed after requests, and the temporary filesystem is discarded when the container stops. A hard process crash can leave files until that container is restarted. HTTPS certificate volumes persist separately and contain no uploaded projects. No analysis history is stored.

## Files to study

- `Dockerfile`: builds React, then packages only the compiled site and Python backend into a non-root runtime.
- `.dockerignore`: excludes local environments, source uploads, reports, credentials, and Git metadata from the build context.
- `deploy/aws/compose.yaml`: runtime limits, restart behavior, private app port, and optional HTTPS proxy.
- `backend/app/frontend.py`: serves the compiled website and applies cache/security headers.
- `backend/app/serve.py`: production server entry point, configured for one API process.
- `.github/workflows/checks.yml`: Linux tests, frontend build, container build/smoke checks, and Compose/Caddy configuration validation; it does not create AWS resources or deploy automatically.
- `scripts/smoke_deployment.py`: checks a running service locally or on EC2.

## Verification boundary

The repository's local verification and GitHub Actions results are separate from AWS verification. Windows can test the app and compiled-site serving, but Docker is not installed on this workstation. The Actions container job must succeed before relying on the Linux image. EC2 launch, DNS, certificate issuance, instance resource behavior, public browser checks, and a real stop/start cycle remain to be verified after account setup.
