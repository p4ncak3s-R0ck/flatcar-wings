# Optional Pterodactyl Panel on Fedora CoreOS

For a fresh Panel installation alongside the Wings service:

```bash
curl -fL https://raw.githubusercontent.com/p4ncak3s-R0ck/flatcar-wings/coreos/coreos/install-panel.sh -o /tmp/install-coreos-panel.sh && sudo bash /tmp/install-coreos-panel.sh
```

The interactive installer asks for `https://panel.example.com` or `http://LAN-IP`, then creates an administrator using Pterodactyl's own CLI. HTTPS requires DNS pointing to this machine and inbound TCP 80/443. It asks for a certificate email and confirmation of Let's Encrypt's terms. HTTP is suitable only for a trusted LAN.

It runs the official Panel v1.15.1 image pinned by digest, MariaDB 11.4, and Redis 7.4 in Docker with restart policies. The upstream Panel image handles its web server, queue worker, scheduler, and database migrations. Only web ports 80/443 are published; database and Redis stay on the Docker network. SELinux remains enabled, with Docker-managed named volumes for persistent data.

Credentials and encryption keys are generated locally and saved with restrictive permissions under `/var/opt/coreos-panel`. Persistent volumes are named `coreos-panel-{database,cache,var,nginx,certs,logs}`. Back up both the credentials directory and volumes, especially the database and `/app/var/.env`. Never generate new encryption keys for an existing Panel. Do not run `docker volume prune` against this installation.

The installer refuses to replace an existing installation or colliding container/network/volume names. If setup fails, it retains state and data for diagnosis; rerunning is intentionally blocked. Inspect the relevant container logs and resolve the failure without deleting database volumes or keys.

SMTP is not configured: mail is written to the Panel's application logs. Configure SMTP before relying on password resets or invitations.

After installation, create a Location and Node in the Panel. Save the node's generated configuration to `/etc/pterodactyl/config.yml` with mode 600 and restart the existing Wings service. Configure the Wings address, its TLS certificates, API/SFTP ports, and game allocations separately. This installer installs the Panel stack; it does not create nodes, replace Wings credentials, change firewall/NAT rules, or configure SMTP.

```bash
sudo docker ps --filter name=coreos-panel
sudo docker logs --tail 100 coreos-panel
sudo docker exec -it coreos-panel php artisan p:user:make --admin=1
sudo systemctl restart wings
```

Checked with Bash syntax validation, ShellCheck, and an isolated mock-container installer smoke check. The upstream image manifest was verified to contain amd64 and arm64 builds. A live CoreOS/Docker/Panel deployment was not available for integration testing.

Sources: [upstream Compose example](https://github.com/pterodactyl/panel/blob/v1.15.1/docker-compose.example.yml), [image entrypoint](https://github.com/pterodactyl/panel/blob/v1.15.1/.github/docker/entrypoint.sh), [stable release](https://github.com/pterodactyl/panel/releases/tag/v1.15.1).
