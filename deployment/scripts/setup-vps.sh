#!/usr/bin/env bash
# =============================================================================
#  setup-vps.sh — Fresh Ubuntu 24.04 VPS provisioning script
#                 for the Personal AI Agent Platform
#
#  Run as root (or via sudo) on a clean Ubuntu 24.04 LTS server:
#    curl -fsSL https://raw.githubusercontent.com/YOU/REPO/main/deployment/scripts/setup-vps.sh | sudo bash
#
#  Or clone the repo and execute locally:
#    sudo bash deployment/scripts/setup-vps.sh
#
#  Required env vars (can be exported before running):
#    REPO_URL   — Git repository URL (e.g. https://github.com/you/agent.git)
#    REPO_BRANCH — Branch to checkout (default: main)
#    APP_DIR     — Installation directory (default: /opt/agent)
#    APP_USER    — System user for the application (default: agentapp)
#    DOMAIN      — Your domain name (informational only at this stage)
# =============================================================================
set -euo pipefail

# ─── Configuration ────────────────────────────────────────────────────────────
REPO_URL="${REPO_URL:-}"
REPO_BRANCH="${REPO_BRANCH:-main}"
APP_DIR="${APP_DIR:-/opt/agent}"
APP_USER="${APP_USER:-agentapp}"
APP_GROUP="${APP_GROUP:-agentapp}"
DOMAIN="${DOMAIN:-}"
LOG_FILE="/var/log/agent-setup.log"

# ─── Helpers ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

log()     { local ts; ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; echo -e "${GREEN}[${ts}] ✓ $*${NC}" | tee -a "${LOG_FILE}"; }
warn()    { local ts; ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; echo -e "${YELLOW}[${ts}] ⚠ $*${NC}" | tee -a "${LOG_FILE}" >&2; }
die()     { local ts; ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"; echo -e "${RED}[${ts}] ✗ $*${NC}" | tee -a "${LOG_FILE}" >&2; exit 1; }
section() { echo -e "\n${YELLOW}══════ $* ══════${NC}" | tee -a "${LOG_FILE}"; }

# ─── Pre-flight checks ────────────────────────────────────────────────────────
[[ "$(id -u)" -eq 0 ]] || die "This script must be run as root"

OS_ID="$(grep '^ID=' /etc/os-release | cut -d= -f2 | tr -d '"')"
OS_VERSION="$(grep '^VERSION_ID=' /etc/os-release | cut -d= -f2 | tr -d '"')"
[[ "${OS_ID}" == "ubuntu" ]] || warn "Expected Ubuntu, got ${OS_ID} — proceeding anyway"
log "Detected OS: ${OS_ID} ${OS_VERSION}"

# ─── Initialise log file ──────────────────────────────────────────────────────
touch "${LOG_FILE}"
chmod 640 "${LOG_FILE}"
log "Setup started — logging to ${LOG_FILE}"

# ═══════════════════════════════════════════════════════════════════════════════
section "1. System update"
# ═══════════════════════════════════════════════════════════════════════════════
export DEBIAN_FRONTEND=noninteractive

apt-get update -qq
apt-get upgrade -y -qq \
    -o Dpkg::Options::="--force-confnew" \
    -o Dpkg::Options::="--force-confdef"
apt-get autoremove -y -qq
log "System packages updated"

# ═══════════════════════════════════════════════════════════════════════════════
section "2. Install base dependencies"
# ═══════════════════════════════════════════════════════════════════════════════
apt-get install -y -qq \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    git \
    unzip \
    htop \
    ncdu \
    jq \
    logrotate \
    ufw \
    fail2ban \
    awscli
log "Base packages installed"

# ═══════════════════════════════════════════════════════════════════════════════
section "3. Install Docker Engine + Compose plugin"
# ═══════════════════════════════════════════════════════════════════════════════
if command -v docker &>/dev/null; then
    warn "Docker already installed — skipping installation"
else
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/ubuntu \
        $(lsb_release -cs) stable" \
        > /etc/apt/sources.list.d/docker.list

    apt-get update -qq
    apt-get install -y -qq \
        docker-ce \
        docker-ce-cli \
        containerd.io \
        docker-buildx-plugin \
        docker-compose-plugin

    systemctl enable --now docker
    log "Docker installed and started"
fi

# Verify
docker version --format '{{.Server.Version}}' | grep -q '.' || die "Docker not running"
docker compose version &>/dev/null || die "Docker Compose plugin not available"
log "Docker $(docker --version | awk '{print $3}' | tr -d ',')"
log "Docker Compose $(docker compose version --short)"

# ═══════════════════════════════════════════════════════════════════════════════
section "4. Create application user and directory"
# ═══════════════════════════════════════════════════════════════════════════════
if id "${APP_USER}" &>/dev/null; then
    warn "User '${APP_USER}' already exists — skipping creation"
else
    groupadd --system "${APP_GROUP}"
    useradd  --system \
             --gid "${APP_GROUP}" \
             --home-dir "${APP_DIR}" \
             --shell /bin/bash \
             --comment "Personal AI Agent application user" \
             "${APP_USER}"
    log "Created system user '${APP_USER}'"
fi

# Add app user to docker group so it can run containers
usermod -aG docker "${APP_USER}"

# Create app directory
mkdir -p "${APP_DIR}"
chown "${APP_USER}:${APP_GROUP}" "${APP_DIR}"
chmod 750 "${APP_DIR}"

# Create backup directory
mkdir -p "${APP_DIR}/backups"
chown "${APP_USER}:${APP_GROUP}" "${APP_DIR}/backups"
chmod 700 "${APP_DIR}/backups"

log "Application directory: ${APP_DIR}"

# ═══════════════════════════════════════════════════════════════════════════════
section "5. Configure UFW firewall"
# ═══════════════════════════════════════════════════════════════════════════════
ufw --force reset

# Default policy
ufw default deny incoming
ufw default allow outgoing

# Allowed inbound ports
ufw allow 22/tcp   comment "SSH"
ufw allow 80/tcp   comment "HTTP"
ufw allow 443/tcp  comment "HTTPS"
ufw allow 443/udp  comment "HTTP/3 QUIC"

# Enable
ufw --force enable
ufw status verbose | tee -a "${LOG_FILE}"
log "UFW firewall configured"

# ═══════════════════════════════════════════════════════════════════════════════
section "6. Harden SSH (disable password auth)"
# ═══════════════════════════════════════════════════════════════════════════════
SSHD_CONFIG="/etc/ssh/sshd_config"

# Only update if key-based auth seems to be in place (known-authorized key file)
if [[ -f /root/.ssh/authorized_keys ]] || [[ -f "/home/${APP_USER}/.ssh/authorized_keys" ]]; then
    sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' "${SSHD_CONFIG}"
    sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin prohibit-password/' "${SSHD_CONFIG}"
    systemctl reload sshd
    log "SSH password authentication disabled"
else
    warn "No authorized_keys found — leaving SSH password auth enabled (add your key first!)"
fi

# ═══════════════════════════════════════════════════════════════════════════════
section "7. Configure log rotation"
# ═══════════════════════════════════════════════════════════════════════════════
cat > /etc/logrotate.d/agent << 'EOF'
/opt/agent/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0640 agentapp agentapp
    sharedscripts
    postrotate
        # Signal Docker containers to reopen log files if needed
        docker kill --signal=USR1 $(docker ps -q --filter "label=app=agent") 2>/dev/null || true
    endscript
}
EOF

/var/log/agent-setup.log {
    weekly
    rotate 4
    compress
    missingok
    notifempty
}
EOF
# NOTE: heredoc above is intentionally indented; the EOF on line above closes it

logrotate --debug /etc/logrotate.d/agent 2>&1 | tail -5 | tee -a "${LOG_FILE}" || true
log "Log rotation configured"

# ═══════════════════════════════════════════════════════════════════════════════
section "8. Configure fail2ban"
# ═══════════════════════════════════════════════════════════════════════════════
cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime  = 3600
findtime = 600
maxretry = 5
backend  = systemd

[sshd]
enabled = true
port    = ssh
logpath = %(sshd_log)s
EOF

systemctl enable --now fail2ban
log "fail2ban configured and started"

# ═══════════════════════════════════════════════════════════════════════════════
section "9. Configure automatic security updates"
# ═══════════════════════════════════════════════════════════════════════════════
apt-get install -y -qq unattended-upgrades

cat > /etc/apt/apt.conf.d/50unattended-upgrades << 'EOF'
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
};
Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::MinimalSteps "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
EOF

echo 'APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";' \
    > /etc/apt/apt.conf.d/20auto-upgrades

log "Automatic security updates configured"

# ═══════════════════════════════════════════════════════════════════════════════
section "10. Set up backup cron"
# ═══════════════════════════════════════════════════════════════════════════════
BACKUP_CRON_FILE="/etc/cron.d/agent-backup"
cat > "${BACKUP_CRON_FILE}" << EOF
# Daily PostgreSQL backup at 02:00 UTC
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
0 2 * * * ${APP_USER} docker exec \$(docker ps -qf "name=agent-postgres") \
    bash -c "cd /app && bash deployment/scripts/backup.sh" \
    >> /var/log/agent-backup.log 2>&1
EOF
chmod 644 "${BACKUP_CRON_FILE}"
log "Backup cron installed: ${BACKUP_CRON_FILE}"

# ═══════════════════════════════════════════════════════════════════════════════
section "11. Clone repository and start services"
# ═══════════════════════════════════════════════════════════════════════════════
if [[ -z "${REPO_URL}" ]]; then
    warn "REPO_URL not set — skipping git clone and service startup"
    warn "To start services manually:"
    warn "  1. cd ${APP_DIR}"
    warn "  2. cp .env.example .env && nano .env"
    warn "  3. docker compose -f deployment/docker-compose.yml up -d"
else
    if [[ -d "${APP_DIR}/.git" ]]; then
        warn "Repository already cloned — pulling latest changes"
        sudo -u "${APP_USER}" git -C "${APP_DIR}" fetch origin
        sudo -u "${APP_USER}" git -C "${APP_DIR}" reset --hard "origin/${REPO_BRANCH}"
    else
        log "Cloning repository from ${REPO_URL} (branch: ${REPO_BRANCH}) ..."
        sudo -u "${APP_USER}" git clone \
            --branch "${REPO_BRANCH}" \
            --depth 1 \
            "${REPO_URL}" \
            "${APP_DIR}"
    fi
    log "Repository ready at ${APP_DIR}"

    if [[ ! -f "${APP_DIR}/.env" ]]; then
        if [[ -f "${APP_DIR}/.env.example" ]]; then
            cp "${APP_DIR}/.env.example" "${APP_DIR}/.env"
            chown "${APP_USER}:${APP_GROUP}" "${APP_DIR}/.env"
            chmod 600 "${APP_DIR}/.env"
            warn ".env created from .env.example — edit it before starting services:"
            warn "  nano ${APP_DIR}/.env"
        else
            warn "No .env.example found — create ${APP_DIR}/.env manually"
        fi
    fi

    if [[ -f "${APP_DIR}/.env" ]]; then
        log "Starting Docker services ..."
        cd "${APP_DIR}"
        sudo -u "${APP_USER}" docker compose \
            -f deployment/docker-compose.yml \
            up -d --build
        log "Services started"
        sudo -u "${APP_USER}" docker compose \
            -f deployment/docker-compose.yml \
            ps
    else
        warn "Skipping docker compose up — .env not configured"
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════════
section "Setup complete"
# ═══════════════════════════════════════════════════════════════════════════════
log "VPS provisioning finished successfully!"
[[ -n "${DOMAIN}" ]] && log "Application will be available at: https://${DOMAIN}"
log "Log file: ${LOG_FILE}"
log "App directory: ${APP_DIR}"
log "App user: ${APP_USER}"
