# GPU Priority Service - Idiap Research Institute

A web service for managing GPU priorities with OIDC authentication using Authlib, PostgreSQL database, and email notifications with SLURM command generation.

## Features

- 🔐 OIDC Authentication using Authlib (Keycloak, Auth0, Google, etc.)
- 🗄️ PostgreSQL database integration  
- 📧 Email notifications for admins and users
- 🖥️ SLURM command generation for GPU priorities (admin-only)
- 📱 Responsive web interface with advanced search and sorting
- 👨‍💼 Enhanced admin panel with search, sort, delete, and messaging capabilities
- 🔒 Input validation and security
- ⏰ Automatic QOS cleanup with "at" command scheduling
- ✅ Priority status management (pending/accepted/refused)
- 📝 Admin messages/communication system
- 🔍 Dynamic search across all priority details
- 🏢 Idiap branding
- ⏱️ Idiap priority policy enforcement
- 📊 Enhanced priority tracking with "Valid until" display
- 🎫 Bugzilla workflow integration

## Prerequisites

- Debian 13 (or compatible Linux distribution)
- Python 3.8+
- PostgreSQL 12+
- OIDC Provider configured
- SMTP server access
- at daemon for scheduled tasks

## Step-by-Step Deployment Guide

### 1. System Update and Package Installation

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install required system packages
sudo apt install -y python3 python3-pip python3-venv postgresql postgresql-contrib nginx supervisor git curl at

# Install additional dependencies
sudo apt install -y libpq-dev python3-dev build-essential

# Install certbot/acme-dns dependencies
sudo apt install -y python3-requests libaugeas0 python3-certbot

# Enable and start at daemon for scheduled tasks
sudo systemctl enable atd
sudo systemctl start atd
```

### 2. PostgreSQL Database Setup

```bash
# Switch to postgres user
sudo -u postgres psql

# In PostgreSQL shell, create database and user:
```
```sql
CREATE DATABASE gpu_priorities;
CREATE USER gpu_user WITH PASSWORD 'your_secure_password_here';
GRANT ALL PRIVILEGES ON DATABASE gpu_priorities TO gpu_user;
ALTER USER gpu_user CREATEDB;
\c gpu_priorities;
GRANT CREATE ON SCHEMA public TO gpu_user;
ALTER SCHEMA public OWNER TO gpu_user;
GRANT CREATE ON SCHEMA public TO gpu_user;
\q
```

```bash
# Test database connection
psql -h localhost -U gpu_user -d gpu_priorities -c "SELECT version();"
```

### 3. Application Setup

```bash
# Create application directory
sudo mkdir -p /opt/gpu-priority-service
sudo chown $USER:$USER /opt/gpu-priority-service
cd /opt/gpu-priority-service

# Extract the project files (if using this archive)
# Or clone from git: git clone <your-repo-url> .

# Create Python virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Environment Configuration

```bash
# Copy and edit environment file
cp .env.example .env

# Edit the .env file with your settings
nano .env
```

Configure the following in `.env`:
- Database connection string
- OIDC provider settings (Client ID, Secret, Discovery URL)  
- Email SMTP settings
- Secret key

### 5. OIDC Provider Configuration

Set these in your `.env` file:
- `OIDC_CLIENT_ID`: Your OIDC client ID
- `OIDC_CLIENT_SECRET`: Your OIDC client secret
- `OIDC_DISCOVERY_URL`: Your OIDC provider's discovery URL

Make sure your OIDC provider has the correct redirect URI: `https://your-domain.com/auth/callback`

### 6. Database Initialization

```bash
# Initialize database tables
source venv/bin/activate
python -c "
from app import create_app
from models import db
app = create_app()
with app.app_context():
    db.create_all()
    print('Database tables created successfully!')
"
```

### 7. Admin User Management

```bash
# Add an admin user
source venv/bin/activate
python manage_admin.py add lillo christophe.lillo@idiap.ch

# List admin users
python manage_admin.py list

# Remove an admin user (if needed)
# python manage_admin.py remove lillo
```

### 8. Test the Application

```bash
# Run development server for testing
source venv/bin/activate
python app.py

# Test in browser: http://localhost:5000
# Press Ctrl+C to stop when testing is complete
```

### 9. Production Deployment with Gunicorn

```bash
# Create Gunicorn configuration
sudo tee /opt/gpu-priority-service/gunicorn.conf.py > /dev/null <<EOL
bind = "127.0.0.1:8000"
workers = 4
worker_class = "sync"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 30
keepalive = 2
preload_app = True
EOL
```

### 10. Systemd Service Configuration

```bash
# Create systemd service file
sudo tee /etc/systemd/system/gpu-priority.service > /dev/null <<EOL
[Unit]
Description=GPU Priority Service
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=exec
User=www-data
Group=www-data
WorkingDirectory=/opt/gpu-priority-service
Environment=PATH=/opt/gpu-priority-service/venv/bin
ExecStart=/opt/gpu-priority-service/venv/bin/gunicorn --config gunicorn.conf.py app:app
ExecReload=/bin/kill -s HUP \$MAINPID
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOL

# Set proper permissions
sudo chown -R www-data:www-data /opt/gpu-priority-service
sudo chmod +x /opt/gpu-priority-service/venv/bin/gunicorn

# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable gpu-priority.service
sudo systemctl start gpu-priority.service

# Check service status
sudo systemctl status gpu-priority.service
```


The system generates these SLURM commands for administrators based on admin-set priority names:

1. **Create QOS**: `sacctmgr add qos <priority_name> GrpTRES=gres/gpu:<gpu_type>=<gpu_count> MaxWall=<duration_in_days>-0 Priority=1000`
2. **Assign QOS to user**: `sacctmgr modify user <username> set qos+=<priority_name> where account=<slurm_project>`
3. **Schedule cleanup**: `at` command to remove QOS after duration expires

### Priority Naming
- Administrators set custom priority names when accepting requests
- Priority names must be valid SLURM QOS names (alphanumeric, underscores, hyphens)
- Commands are regenerated automatically when usernames are modified

## Usage

1. **Access the Application**: Navigate to your domain in a web browser
2. **Login**: Use OIDC authentication to log in
3. **Open Bugzilla Ticket**: Create ticket and get PI approval
4. **Create Priority**: Fill out the priority form with required details (maximum 14 days)
5. **Admin Panel**: Admins can search, sort, manage status, set priority names, and add messages
6. **Priority Acceptance**: When accepting, admin sets custom priority name for SLURM
7. **User Management**: Admin can add/remove users from existing priorities
8. **Internal Messaging**: Admin can add messages visible in user's priority list
9. **My Priorities**: Users can view their priorities in list format with expandable details
10. **Archive Management**: Toggle between active and archived priority views
11. **Email Notifications**: Automatic emails sent for status changes


## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   ```bash
   # Check PostgreSQL status
   sudo systemctl status postgresql

   # Test database connection
   psql -h localhost -U gpu_user -d gpu_priorities
   ```

2. **Application Won't Start**
   ```bash
   # Check service logs
   sudo journalctl -u gpu-priority.service -f

   # Test manually
   cd /opt/gpu-priority-service
   source venv/bin/activate
   python app.py
   ```

3. **OIDC Authentication Issues**
   - Verify environment variables for OIDC configuration
   - Check OIDC provider settings and discovery URL
   - Ensure redirect URIs are configured correctly in your OIDC provider

4. **Admin Panel Access Issues**
   - Verify user is added to admin_users table
   - Check admin username matches OIDC username exactly
   - Use manage_admin.py script to add admin users

5. **Duration Validation Issues**
   - Ensure duration is between 1 and 14 days
   - Check both client-side and server-side validation
   - Review form input max attribute

6. **Policy Tooltip Issues**
   - Ensure Bootstrap tooltips are properly initialized
   - Check for JavaScript console errors
   - Verify HTML content in tooltip is valid

7. **Form Layout Issues**
   - Verify Bootstrap grid classes are correctly applied
   - Test responsive behavior on different screen sizes
   - Check CSS media queries for mobile compatibility

## Security Considerations

- Keep all dependencies updated
- Use strong passwords and secure secrets
- Configure firewall properly
- Enable SSL/TLS encryption
- Regular security audits
- Monitor logs for suspicious activity
- Backup data regularly
- Validate all user inputs including priority names
- Implement proper access controls for admin functions
- Ensure admin-only features are properly protected

## Support

For issues and questions:
1. Check the logs for error messages
2. Verify configuration files
3. Test individual components
4. Review OIDC provider documentation
5. Check timezone configuration if timestamps appear incorrect
