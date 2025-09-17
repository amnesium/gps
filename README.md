# GPU Priority Service - Idiap Research Institute (Enhanced)

A web service for managing GPU priorities with OIDC authentication using Authlib, PostgreSQL database, and email notifications with SLURM command generation. **This enhanced version includes dynamic GPU availability display and validation.**

## ✨ New Features Added

- **🔍 Dynamic GPU Availability Display**: Visual representation of available GPUs above the form fields
- **📊 Real-time GPU Monitoring**: GPU dropdown and validation based on `/usr/local/bin/remaining-gpus-for-prio.sh` script output  
- **⚡ Live Validation**: Number of GPUs field validates against actual availability
- **🏢 Enlarged Company Logo**: Idiap logo displayed 40% larger in footer
- **🔄 Auto-refresh**: GPU availability refreshes every 30 seconds

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
- **🎯 Dynamic GPU Availability Integration** *(NEW)*
- **📈 Visual GPU Usage Bars** *(NEW)*
- **🔄 Real-time Validation** *(NEW)*

## Prerequisites

- Debian 13 (or compatible Linux distribution)
- Python 3.8+
- PostgreSQL 12+
- OIDC Provider configured
- SMTP server access
- at daemon for scheduled tasks
- **GPU monitoring script at `/usr/local/bin/remaining-gpus-for-prio.sh`** *(NEW)*

## GPU Monitoring Script

The enhanced version requires a script at `/usr/local/bin/remaining-gpus-for-prio.sh` that outputs GPU availability in the following format:

```bash
#!/bin/bash
# Example script - replace with your actual implementation
echo "v100 4"
echo "h100 0" 
echo "rtx3090 30"
```

The script should output:
- First column: GPU model name (lowercase)
- Second column: Number of available GPUs
- One line per GPU type

Make sure the script is executable:
```bash
sudo chmod +x /usr/local/bin/remaining-gpus-for-prio.sh
```

## Step-by-Step Deployment Guide

### 1. System Update and Package Installation

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install required system packages
sudo apt install -y python3 python3-pip python3-venv postgresql postgresql-contrib nginx supervisor git curl at

# Install additional dependencies
sudo apt install -y libpq-dev python3-dev build-essential bc

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

# Extract the project files
unzip gpu-priority-service-enhanced.zip
cd gpu-priority-service-enhanced

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

Make sure your OIDC provider has the correct redirect URI:
```
https://your-domain.com/auth/callback
```

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
# Add admin users
source venv/bin/activate
python manage_admin.py add lillo christophe.lillo@idiap.ch
python manage_admin.py add baco guy.baconniere@idiap.ch
python manage_admin.py add lmplumel louis-marie.plumel@idiap.ch
python manage_admin.py add formaz frank.formaz@idiap.ch
python manage_admin.py add ltomas laurent.tomas@idiap.ch

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
ExecReload=/bin/kill -s HUP $MAINPID
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

## Enhanced Features Details

### GPU Availability Display

- **Visual Bars**: Shows available GPUs for each type with colored progress bars
- **Auto-refresh**: Updates every 30 seconds automatically
- **Status Colors**: 
  - Green: Good availability (≥10 GPUs)
  - Yellow: Limited availability (1-9 GPUs)
  - Red: No availability (0 GPUs)

### Dynamic Validation  

- **Dropdown Population**: GPU types populated from script output
- **Count Validation**: Prevents requesting more GPUs than available
- **Real-time Feedback**: Immediate validation as user types
- **Fallback Handling**: Graceful degradation if script fails

### API Endpoints

- **`/api/available-gpus`**: Returns current GPU availability as JSON
- Used by frontend for real-time updates
- Secured with login requirement

## Usage

1. **Access the Application**: Navigate to your domain in a web browser
2. **Login**: Use OIDC authentication to log in
3. **Open Bugzilla Ticket**: Create ticket and get PI approval
4. **Create Priority**: Fill out the priority form - **now shows real-time GPU availability**
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

3. **GPU Script Issues** *(NEW)*

   ```bash
   # Test script manually
   /usr/local/bin/remaining-gpus-for-prio.sh

   # Check script permissions
   ls -la /usr/local/bin/remaining-gpus-for-prio.sh

   # Make executable if needed
   sudo chmod +x /usr/local/bin/remaining-gpus-for-prio.sh

   # Check application logs for script errors
   sudo journalctl -u gpu-priority.service -f | grep -i gpu
   ```

4. **OIDC Authentication Issues**

   - Verify environment variables for OIDC configuration
   - Check OIDC provider settings and discovery URL
   - Ensure redirect URIs are configured correctly in your OIDC provider

5. **Admin Panel Access Issues**

   - Verify user is added to admin_users table
   - Check admin username matches OIDC username exactly
   - Use manage_admin.py script to add admin users

## New Configuration Options

The enhanced version includes additional configuration for GPU monitoring:

- GPU script timeout: 10 seconds (hardcoded, modify `utils.py` if needed)
- GPU refresh interval: 30 seconds (hardcoded in JavaScript)
- Fallback GPU types: `rtx3090`, `v100`, `h100`

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
- **Secure GPU script execution**: Script runs with application permissions

## Support

For issues and questions:

1. Check the logs for error messages
2. Verify configuration files
3. Test individual components
4. Review OIDC provider documentation
5. Check timezone configuration if timestamps appear incorrect
6. **Test GPU monitoring script independently**
7. **Check network connectivity for AJAX requests**

## Changes from Original

### Modified Files:
- `app.py`: Added GPU availability API endpoint and validation
- `utils.py`: Added `get_available_gpus()` function
- `templates/priority.html`: Enhanced with GPU availability display
- `templates/base.html`: Enlarged company logo (40% bigger)
- `static/css/style.css`: Added GPU availability styling
- `static/js/custom.js`: Added GPU validation JavaScript

### New Features:
- Dynamic GPU type dropdown population
- Visual GPU availability display with progress bars
- Real-time form validation against available GPUs
- Auto-refresh of GPU availability data
- API endpoint for GPU data
- Enhanced error handling for script failures
- Fallback GPU types for script failures

### Dependencies:
- No new Python dependencies required
- Uses existing Flask, subprocess, and JavaScript frameworks
- Compatible with all existing features

## About

Enhanced version with dynamic GPU availability integration.
No description, website, or topics provided.

### Resources

Readme
Activity

### Stars

**0** stars

### Watchers  

**0** watching

### Forks

**0** forks

## Releases

No releases published

## Packages 0

No packages published

## Languages

- HTML 51.9%
- Python 34.8% 
- JavaScript 7.5%
- CSS 5.8%
