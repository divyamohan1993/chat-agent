#!/bin/bash
# =============================================================================
# RealtyAssistant AI Agent - One-Click VM Deployment Script
# =============================================================================
# This script is IDEMPOTENT - safe to run multiple times.
# Run with: sudo bash run_project.sh
# Deploys to: reas.dmj.one/task1/
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="realtyassistant"
APP_PORT=20000
DOMAIN="reas.dmj.one"
LOCATION_PATH="/task1"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
SERVICE_NAME="${APP_NAME}.service"
NGINX_CONF="/etc/nginx/sites-available/${APP_NAME}"
NGINX_ENABLED="/etc/nginx/sites-enabled/${APP_NAME}"

echo -e "${BLUE}"
echo "============================================================"
echo "   RealtyAssistant AI Agent - One-Click VM Deployment"
echo "============================================================"
echo -e "${NC}"

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}[ERROR] Please run with sudo: sudo bash run_project.sh${NC}"
    exit 1
fi

# Get the actual user (not root)
REAL_USER="${SUDO_USER:-$(whoami)}"
REAL_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)

# =============================================================================
# STEP 1: System Update & Dependencies
# =============================================================================
echo -e "${YELLOW}[1/10] Updating system and installing dependencies...${NC}"

apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv nginx curl git

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}   Python ${PYTHON_VERSION} installed${NC}"

# =============================================================================
# STEP 2: Create/Verify Virtual Environment
# =============================================================================
echo -e "${YELLOW}[2/10] Setting up Python virtual environment...${NC}"

if [ ! -d "$VENV_DIR" ]; then
    echo "   Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    chown -R "$REAL_USER:$REAL_USER" "$VENV_DIR"
    echo -e "${GREEN}   Virtual environment created${NC}"
else
    echo -e "${GREEN}   Virtual environment already exists${NC}"
fi

# =============================================================================
# STEP 3: Install Python Dependencies
# =============================================================================
echo -e "${YELLOW}[3/10] Installing Python dependencies...${NC}"

# Activate venv and install
source "$VENV_DIR/bin/activate"
pip install --upgrade pip -q
pip install -r "$PROJECT_DIR/requirements.txt" -q 2>/dev/null || {
    echo "   Installing core packages individually..."
    pip install fastapi uvicorn python-dotenv rich pydantic -q
    pip install google-generativeai ollama httpx aiohttp -q
    pip install playwright beautifulsoup4 lxml -q
    pip install tenacity pydantic-settings python-multipart sqlalchemy -q
}
echo -e "${GREEN}   Dependencies installed${NC}"

# =============================================================================
# STEP 4: Install Playwright Browsers
# =============================================================================
echo -e "${YELLOW}[4/10] Installing Playwright browsers...${NC}"

# Install playwright browsers
# 1. Install system dependencies (requires root)
echo "   Installing Playwright system dependencies..."
"$VENV_DIR/bin/playwright" install-deps chromium || echo "   Warning: Failed to install system deps, continuing..."

# 2. Install binaries as the REAL USER (so they go to ~/.cache/ms-playwright)
echo "   Installing Playwright browsers for user $REAL_USER..."
sudo -u "$REAL_USER" "$VENV_DIR/bin/playwright" install chromium || echo "   Warning: Failed to install browsers as user"

echo -e "${GREEN}   Playwright ready${NC}"

# =============================================================================
# STEP 5: Create Required Directories
# =============================================================================
echo -e "${YELLOW}[5/10] Creating application directories...${NC}"

mkdir -p "$PROJECT_DIR/data/logs"
mkdir -p "$PROJECT_DIR/data/leads"
mkdir -p "$PROJECT_DIR/data/emails"
mkdir -p "$PROJECT_DIR/data/email_queue"
chown -R "$REAL_USER:$REAL_USER" "$PROJECT_DIR/data"
echo -e "${GREEN}   Directories created${NC}"

# =============================================================================
# STEP 6: Create/Update .env Configuration
# =============================================================================
echo -e "${YELLOW}[6/10] Setting up environment configuration...${NC}"

if [ ! -f "$PROJECT_DIR/.env" ]; then
    if [ -f "$PROJECT_DIR/.env.example" ]; then
        cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    else
        cat > "$PROJECT_DIR/.env" << 'ENVFILE'
# RealtyAssistant Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma3:1b
LLM_TIMEOUT_SECONDS=3.5
ENABLE_GEMINI_FALLBACK=true
GEMINI_API_KEY=
LOGS_DIR=data/logs
LEADS_DIR=data/leads
HOST=127.0.0.1
PORT=20000
ENVFILE
    fi
    chown "$REAL_USER:$REAL_USER" "$PROJECT_DIR/.env"
    echo -e "${GREEN}   Created .env configuration${NC}"
else
    echo -e "${GREEN}   .env already exists${NC}"
fi

# =============================================================================
# STEP 7: Create Startup Wrapper & Systemd Service
# =============================================================================
echo -e "${YELLOW}[7/10] Creating auto-update startup wrapper...${NC}"

# Create a wrapper script that updates code/deps on boot
WRAPPER_SCRIPT="$PROJECT_DIR/start_agent.sh"
cat > "$WRAPPER_SCRIPT" << WRAPPEREOF
#!/bin/bash
# Auto-generated startup script
cd "$PROJECT_DIR"

# 1. Update Code
echo "Checking for updates..."
if command -v git &> /dev/null; then
    git pull origin main || echo "Git pull failed or not a git repo, continuing..."
else
    echo "Git not found, skipping update."
fi

# 2. Update Dependencies
source "$VENV_DIR/bin/activate"
pip install -r requirements.txt -q
playwright install chromium

# 3. Start Application
exec python main.py serve --host 127.0.0.1 --port ${APP_PORT}
WRAPPEREOF

chmod +x "$WRAPPER_SCRIPT"
chown "$REAL_USER:$REAL_USER" "$WRAPPER_SCRIPT"

echo -e "${GREEN}   Startup wrapper created${NC}"
echo -e "${YELLOW}   Creating systemd service...${NC}"

cat > "/etc/systemd/system/${SERVICE_NAME}" << SERVICEEOF
[Unit]
Description=RealtyAssistant AI Agent
After=network.target

[Service]
Type=simple
User=${REAL_USER}
Group=${REAL_USER}
WorkingDirectory=${PROJECT_DIR}
Environment="PATH=${VENV_DIR}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
# Run the wrapper script instead of python directly
ExecStart=${WRAPPER_SCRIPT}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICEEOF

echo -e "${GREEN}   Systemd service created${NC}"

# Reload systemd and enable service
systemctl daemon-reload
systemctl enable "$SERVICE_NAME" 2>/dev/null

# =============================================================================
# STEP 8: Configure Nginx
# =============================================================================
echo -e "${YELLOW}[8/10] Configuring Nginx...${NC}"

cat > "$NGINX_CONF" << NGINXEOF
# RealtyAssistant AI Agent - Nginx Configuration
# Domain: ${DOMAIN}
# Location: ${LOCATION_PATH}

server {
    listen 80;
    server_name ${DOMAIN};

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # RealtyAssistant API and Frontend - Task 1
    location ${LOCATION_PATH}/ {
        proxy_pass http://127.0.0.1:${APP_PORT}/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header X-Forwarded-Prefix ${LOCATION_PATH};
        proxy_read_timeout 86400;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        
        # Handle trailing slash
        proxy_redirect / ${LOCATION_PATH}/;
    }

    # Static files for Task 1
    location ${LOCATION_PATH}/static/ {
        proxy_pass http://127.0.0.1:${APP_PORT}/static/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    # Widget JS
    location = ${LOCATION_PATH}/widget.js {
        proxy_pass http://127.0.0.1:${APP_PORT}/widget.js;
        proxy_set_header Host \$host;
        add_header Content-Type "application/javascript";
        expires 1d;
    }

    # Demo page redirect
    location = ${LOCATION_PATH} {
        return 301 ${LOCATION_PATH}/demo;
    }

    # Health check
    location = ${LOCATION_PATH}/health {
        proxy_pass http://127.0.0.1:${APP_PORT}/api/status;
        proxy_set_header Host \$host;
    }

    # Error pages
    error_page 502 503 504 /50x.html;
    location = /50x.html {
        root /usr/share/nginx/html;
        internal;
    }
}
NGINXEOF

# Enable site
ln -sf "$NGINX_CONF" "$NGINX_ENABLED" 2>/dev/null || true

# Remove default site if it conflicts
if [ -f "/etc/nginx/sites-enabled/default" ]; then
    rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
fi

# Test nginx configuration
nginx -t 2>/dev/null || {
    echo -e "${RED}   [ERROR] Nginx configuration test failed${NC}"
    exit 1
}

echo -e "${GREEN}   Nginx configured${NC}"

# =============================================================================
# STEP 9: Start/Restart Services
# =============================================================================
echo -e "${YELLOW}[9/10] Starting services...${NC}"

# Stop any existing instance
systemctl stop "$SERVICE_NAME" 2>/dev/null || true

# Kill any process on the port
fuser -k ${APP_PORT}/tcp 2>/dev/null || true
sleep 2

# Start the application service
systemctl start "$SERVICE_NAME"

# Restart nginx
systemctl restart nginx

# Wait for app to be ready
echo "   Waiting for application to start..."
sleep 5

# Check if service is running
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo -e "${GREEN}   Application service running${NC}"
else
    echo -e "${RED}   [WARNING] Service may not have started properly${NC}"
    echo "   Check logs with: sudo journalctl -u $SERVICE_NAME -f"
fi

if systemctl is-active --quiet nginx; then
    echo -e "${GREEN}   Nginx running${NC}"
else
    echo -e "${RED}   [ERROR] Nginx not running${NC}"
fi

# =============================================================================
# STEP 10: Verify Deployment
# =============================================================================
echo -e "${YELLOW}[10/10] Verifying deployment...${NC}"

# Test local endpoint
if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${APP_PORT}/" | grep -q "200"; then
    echo -e "${GREEN}   ✓ Local API responding${NC}"
else
    echo -e "${YELLOW}   ⚠ Local API may still be starting...${NC}"
fi

# =============================================================================
# DEPLOYMENT COMPLETE
# =============================================================================
echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}   DEPLOYMENT COMPLETE!${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo -e "${BLUE}   Access Points:${NC}"
echo -e "   • Demo UI:     http://${DOMAIN}${LOCATION_PATH}/demo"
echo -e "   • Voice UI:    http://${DOMAIN}${LOCATION_PATH}/voice"
echo -e "   • API:         http://${DOMAIN}${LOCATION_PATH}/api/status"
echo -e "   • Widget:      http://${DOMAIN}${LOCATION_PATH}/widget.js"
echo ""
echo -e "${BLUE}   Management Commands:${NC}"
echo -e "   • View logs:    sudo journalctl -u ${SERVICE_NAME} -f"
echo -e "   • Restart app:  sudo systemctl restart ${SERVICE_NAME}"
echo -e "   • Stop app:     sudo systemctl stop ${SERVICE_NAME}"
echo -e "   • Restart nginx: sudo systemctl restart nginx"
echo ""
echo -e "${YELLOW}   Note: Point your DNS A record for ${DOMAIN} to this VM's IP${NC}"
echo ""
echo -e "${GREEN}============================================================${NC}"
