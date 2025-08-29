from flask import Flask, render_template, request, redirect, url_for, session, flash, g, jsonify
from flask_sqlalchemy import SQLAlchemy
from authlib.integrations.flask_client import OAuth
from flask_mail import Mail, Message
from config import Config
from models import db, User, Priority, AdminUser
from utils import get_or_create_user, generate_slurm_command, validate_bugzilla_ticket, validate_username, is_admin_user, validate_priority_name
import logging
from datetime import datetime, timedelta
import pytz
from functools import wraps
import secrets
import re
import threading
from concurrent.futures import ThreadPoolExecutor
import time

# Define timezone
TIMEZONE = pytz.timezone('Europe/Zurich')

# Thread pool for async operations
email_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="email_")

def utc_to_zurich(utc_dt):
    """Convert UTC datetime to Europe/Zurich timezone"""
    if utc_dt is None:
        return None
    if utc_dt.tzinfo is None:
        utc_dt = pytz.utc.localize(utc_dt)
    return utc_dt.astimezone(TIMEZONE)

def zurich_now():
    """Get current time in Europe/Zurich timezone"""
    return datetime.now(TIMEZONE)

def send_email_async(mail_instance, msg, app_instance, priority_id):
    """Send email asynchronously with timeout and error handling"""
    def send_with_timeout():
        try:
            with app_instance.app_context():
                mail_instance.send(msg)
                app_instance.logger.info(f'Email sent successfully for priority {priority_id}')
        except Exception as e:
            app_instance.logger.error(f'Failed to send email for priority {priority_id}: {str(e)}')

    # Submit to thread pool with timeout
    try:
        future = email_executor.submit(send_with_timeout)
        # Don't wait for completion to avoid blocking
    except Exception as e:
        app_instance.logger.error(f'Failed to submit email task for priority {priority_id}: {str(e)}')

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    oauth = OAuth(app)
    mail = Mail(app)

    # Configure OIDC client
    oauth.register(
        name='oidc',
        client_id=app.config['OIDC_CLIENT_ID'],
        client_secret=app.config['OIDC_CLIENT_SECRET'],
        server_metadata_url=app.config['OIDC_DISCOVERY_URL'],
        client_kwargs={
            'scope': 'openid email profile'
        }
    )

    # Configure logging
    if not app.debug:
        logging.basicConfig(level=logging.INFO)

    # Add timezone helper to template context
    @app.template_filter('zurich_time')
    def zurich_time_filter(utc_dt):
        return utc_to_zurich(utc_dt)

    # Add is_admin_user function to template context
    @app.template_global('is_admin_user')
    def template_is_admin_user(username):
        return is_admin_user(username)

    def login_required(f):
        """Decorator to require authentication"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if g.user is None:
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function

    def admin_required(f):
        """Decorator to require admin access"""
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if g.user is None:
                return redirect(url_for('login'))

            if not is_admin_user(g.user.username):
                flash('Access denied. Admin privileges required.', 'error')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function

    @app.before_request
    def before_request():
        user_data = session.get('user')
        if user_data:
            g.user = get_or_create_user(user_data)
        else:
            g.user = None

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/login')
    def login():
        nonce = secrets.token_urlsafe(16)
        session['oidc_nonce'] = nonce
        redirect_uri = url_for('auth_callback', _external=True)
        return oauth.oidc.authorize_redirect(redirect_uri, nonce=nonce)

    @app.route('/auth/callback')
    def auth_callback():
        try:
            token = oauth.oidc.authorize_access_token()
            if not token:
                flash('Authentication failed. Please try again.', 'error')
                return redirect(url_for('index'))

            nonce = session.pop('oidc_nonce', None)
            user_info = oauth.oidc.parse_id_token(token, nonce=nonce)
            if not user_info:
                flash('Failed to get user information from OIDC provider.', 'error')
                return redirect(url_for('index'))

            # Store user info in session
            session['user'] = {
                'sub': user_info.get('sub'),
                'email': user_info.get('email', ''),
                'preferred_username': user_info.get('preferred_username', ''),
                'given_name': user_info.get('given_name', ''),
                'family_name': user_info.get('family_name', ''),
            }

            flash('Successfully logged in!', 'success')
            return redirect(url_for('priority_form'))

        except Exception as e:
            app.logger.error(f'OIDC callback error: {str(e)}')
            flash('Authentication error occurred. Please try again.', 'error')
            return redirect(url_for('index'))

    @app.route('/logout')
    def logout():
        session.clear()
        flash('You have been logged out successfully.', 'info')
        return redirect(url_for('index'))

    @app.route('/priority')
    @login_required
    def priority_form():
        gpu_types = ['rtx3090', 'v100', 'h100']

        # Get form data from session if available (for form preservation)
        form_data = session.pop('form_data', {})
        if not form_data:
            form_data = {'username': g.user.username}

        return render_template('priority.html', gpu_types=gpu_types, form_data=form_data)

    @app.route('/submit_priority', methods=['POST'])
    @login_required
    def submit_priority():
        # Get form data
        data = {
            'bugzilla_ticket': request.form.get('bugzilla_ticket', '').strip(),
            'username': request.form.get('username', '').strip(),
            'additional_usernames': request.form.get('additional_usernames', '').strip(),
            'slurm_project': request.form.get('slurm_project', '').strip(),
            'gpu_type': request.form.get('gpu_type', ''),
            'gpu_count': int(request.form.get('gpu_count', 0) or 0),
            'duration_days': int(request.form.get('duration_days', 0) or 0),
            'reason': request.form.get('reason', '').strip()
        }

        # Validation
        errors = []

        if not validate_bugzilla_ticket(data['bugzilla_ticket']):
            errors.append('Invalid Bugzilla ticket format')

        if not data['username']:
            errors.append('Username is required')

        if data['additional_usernames'] and not validate_username(data['additional_usernames']):
            errors.append('Invalid additional usernames format')

        if not data['slurm_project'] or not validate_username(data['slurm_project']):
            errors.append('Valid SLURM project is required')

        if not data['gpu_type'] or data['gpu_type'] not in ['rtx3090', 'v100', 'h100']:
            errors.append('Valid GPU type is required')

        if not data['gpu_count'] or data['gpu_count'] < 1:
            errors.append('GPU count must be at least 1')

        # Enforce maximum duration of 2 weeks (14 days)
        if not data['duration_days'] or data['duration_days'] < 1 or data['duration_days'] > 14:
            errors.append('Duration must be between 1 and 14 days (maximum 2 weeks)')

        if not data['reason']:
            errors.append('Reason is required')

        if errors:
            # Preserve form data for user convenience
            session['form_data'] = data
            for error in errors:
                flash(error, 'error')
            return redirect(url_for('priority_form'))

        # Store in session for confirmation
        session['priority_data'] = data
        return render_template('confirm_priority.html', data=data)

    @app.route('/confirm_priority', methods=['POST'])
    @login_required
    def confirm_priority():
        start_time = time.time()

        data = session.get('priority_data')
        if not data:
            app.logger.warning(f'No priority data found in session for user {g.user.username}')
            flash('No priority data found. Please fill out the form again.', 'error')
            return redirect(url_for('priority_form'))

        # Validate user ID exists
        if not g.user or not g.user.id:
            app.logger.error(f'Invalid user object during priority confirmation: {g.user}')
            flash('Session expired. Please log in again.', 'error')
            return redirect(url_for('login'))

        priority = None
        try:
            # Create priority object first (without database operations)
            app.logger.info(f'Creating priority for user {g.user.username} (ID: {g.user.id})')

            priority = Priority(
                user_id=g.user.id,
                bugzilla_ticket=data['bugzilla_ticket'],
                additional_usernames=data['additional_usernames'] if data['additional_usernames'] else None,
                slurm_project=data['slurm_project'],
                gpu_type=data['gpu_type'],
                gpu_count=data['gpu_count'],
                duration_days=data['duration_days'],
                reason=data['reason']
            )

            # Database operations with explicit transaction
            app.logger.info(f'Saving priority to database for ticket {data["bugzilla_ticket"]}')
            db.session.add(priority)
            db.session.flush()  # Get the ID without committing
            priority_id = priority.id
            db.session.commit()

            app.logger.info(f'Priority {priority_id} saved successfully in {time.time() - start_time:.2f}s')

            # Clear session data immediately after successful save
            session.pop('priority_data', None)

            # Send emails asynchronously (non-blocking)
            try:
                send_priority_emails_async(priority, mail, app)
            except Exception as email_error:
                # Don't fail the whole operation if email fails
                app.logger.error(f'Email sending failed for priority {priority_id}: {str(email_error)}')

            flash('Priority submitted successfully!', 'success')
            return redirect(url_for('my_priorities'))

        except Exception as e:
            # Rollback any database changes
            db.session.rollback()

            error_msg = str(e)
            app.logger.error(f'Error creating priority for user {g.user.username}: {error_msg}')

            # More specific error messages
            if 'duplicate key' in error_msg.lower():
                flash('A priority with this Bugzilla ticket already exists.', 'error')
            elif 'foreign key' in error_msg.lower():
                flash('Invalid user data. Please log in again.', 'error')
                return redirect(url_for('login'))
            elif 'not-null' in error_msg.lower():
                flash('Missing required data. Please fill out the form completely.', 'error')
            else:
                flash('Error creating priority. Please try again.', 'error')

            return redirect(url_for('priority_form'))

    @app.route('/edit_priority')
    @login_required
    def edit_priority():
        # Get priority data from session and preserve it for editing
        data = session.get('priority_data')
        if data:
            session['form_data'] = data
        return redirect(url_for('priority_form'))

    @app.route('/my_priorities')
    @login_required
    def my_priorities():
        show_archived = request.args.get('show_archived', 'false').lower() == 'true'

        # Optimized database query with eager loading
        query = Priority.query.filter_by(user_id=g.user.id).options(
            db.joinedload(Priority.user)
        )
        priorities = query.all()

        if not show_archived:
            # Filter out archived priorities (expired for more than 7 days)
            current_time = datetime.utcnow()
            filtered_priorities = []

            for priority in priorities:
                should_include = True

                # Check if priority should be archived
                if priority.status == 'accepted' and priority.status_updated_at:
                    expiry_date = priority.status_updated_at + timedelta(days=priority.duration_days)
                    archive_cutoff = expiry_date + timedelta(days=7)

                    if current_time > archive_cutoff:
                        should_include = False

                if should_include:
                    filtered_priorities.append(priority)

            priorities = filtered_priorities

        # Sort by created_at descending
        priorities = sorted(priorities, key=lambda x: x.created_at, reverse=True)

        return render_template('my_priorities.html', priorities=priorities, show_archived=show_archived, 
                             utc_to_zurich=utc_to_zurich)

    @app.route('/admin')
    @admin_required
    def admin_panel():
        show_archived = request.args.get('show_archived', 'false').lower() == 'true'

        # Optimized database query with eager loading
        query = Priority.query.options(
            db.joinedload(Priority.user)
        )
        priorities = query.all()

        if not show_archived:
            # Filter out archived priorities (expired for more than 7 days)
            current_time = datetime.utcnow()
            filtered_priorities = []

            for priority in priorities:
                should_include = True

                # Check if priority should be archived
                if priority.status == 'accepted' and priority.status_updated_at:
                    expiry_date = priority.status_updated_at + timedelta(days=priority.duration_days)
                    archive_cutoff = expiry_date + timedelta(days=7)

                    if current_time > archive_cutoff:
                        should_include = False

                if should_include:
                    filtered_priorities.append(priority)

            priorities = filtered_priorities

        # Sort by created_at descending
        priorities = sorted(priorities, key=lambda x: x.created_at, reverse=True)

        return render_template('admin.html', priorities=priorities, show_archived=show_archived)

    @app.route('/update_priority_status', methods=['POST'])
    @admin_required
    def update_priority_status():
        priority_id = request.form.get('priority_id')
        new_status = request.form.get('status')
        admin_message = request.form.get('admin_message', '').strip()
        priority_name = request.form.get('priority_name', '').strip()

        if not priority_id or new_status not in ['pending', 'accepted', 'refused']:
            flash('Invalid priority or status', 'error')
            return redirect(url_for('admin_panel'))

        # If accepting, priority name is required
        if new_status == 'accepted' and not priority_name:
            flash('Priority name is required when accepting a priority', 'error')
            return redirect(url_for('admin_panel'))

        # Validate priority name
        if priority_name and not validate_priority_name(priority_name):
            flash('Invalid priority name. Use only letters, numbers, underscores, and hyphens', 'error')
            return redirect(url_for('admin_panel'))

        try:
            priority = Priority.query.get_or_404(priority_id)
            old_status = priority.status
            old_priority_name = priority.priority_name

            priority.status = new_status
            priority.status_updated_at = datetime.utcnow()
            priority.status_updated_by = g.user.username

            # Handle admin message with timestamp
            if admin_message:
                zurich_time = zurich_now()
                timestamp = zurich_time.strftime('%Y-%m-%d %H:%M')
                new_message = f"[{timestamp}] {g.user.username}: {admin_message}"

                if priority.admin_message:
                    priority.admin_message += f"\n\n{new_message}"
                else:
                    priority.admin_message = new_message

            # Set priority name only when accepting
            if new_status == 'accepted':
                priority.priority_name = priority_name
                # Generate SLURM commands with the new priority name
                priority.slurm_command = generate_slurm_command(priority)

                # Add automatic acceptance message with timestamp if no manual message was provided
                if not admin_message:
                    zurich_time = zurich_now()
                    timestamp = zurich_time.strftime('%Y-%m-%d %H:%M')
                    acceptance_message = f"[{timestamp}] {g.user.username}: Priority accepted and configured with name '{priority_name}'"

                    if priority.admin_message:
                        priority.admin_message += f"\n\n{acceptance_message}"
                    else:
                        priority.admin_message = acceptance_message

            elif new_status == 'refused':
                # Clear priority name and SLURM commands if refused
                priority.priority_name = None
                priority.slurm_command = None

            db.session.commit()

            # Send email notification asynchronously
            try:
                send_status_update_email_async(priority, old_status, mail, app)
            except Exception as email_error:
                app.logger.error(f'Email sending failed for priority {priority_id}: {str(email_error)}')

            flash(f'Priority {priority_id} status updated to {new_status}', 'success')

        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Error updating priority status: {str(e)}')
            flash('Error updating priority status', 'error')

        return redirect(url_for('admin_panel'))

    @app.route('/update_priority_users', methods=['POST'])
    @admin_required
    def update_priority_users():
        priority_id = request.form.get('priority_id')
        additional_usernames = request.form.get('additional_usernames', '').strip()

        if not priority_id:
            flash('Invalid priority ID', 'error')
            return redirect(url_for('admin_panel'))

        # Validate additional usernames if provided
        if additional_usernames and not validate_username(additional_usernames):
            flash('Invalid additional usernames format', 'error')
            return redirect(url_for('admin_panel'))

        try:
            priority = Priority.query.get_or_404(priority_id)
            old_usernames = priority.additional_usernames

            priority.additional_usernames = additional_usernames if additional_usernames else None

            # Regenerate SLURM commands if priority is accepted and has priority name
            if priority.status == 'accepted' and priority.priority_name:
                priority.slurm_command = generate_slurm_command(priority)

            db.session.commit()

            flash(f'Priority {priority_id} users updated successfully', 'success')
            app.logger.info(f'Priority {priority_id} users updated by admin {g.user.username}')

        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Error updating priority users {priority_id}: {str(e)}')
            flash('Error updating priority users', 'error')

        return redirect(url_for('admin_panel'))

    @app.route('/add_message', methods=['POST'])
    @admin_required
    def add_message():
        priority_id = request.form.get('priority_id')
        message = request.form.get('message', '').strip()

        if not priority_id or not message:
            flash('Priority ID and message are required', 'error')
            return redirect(url_for('admin_panel'))

        try:
            priority = Priority.query.get_or_404(priority_id)

            # Append message to existing admin message or create new one
            zurich_time = zurich_now()
            timestamp = zurich_time.strftime('%Y-%m-%d %H:%M')
            new_message = f"[{timestamp}] {g.user.username}: {message}"

            if priority.admin_message:
                priority.admin_message += f"\n\n{new_message}"
            else:
                priority.admin_message = new_message

            db.session.commit()

            flash(f'Message added to priority {priority_id}', 'success')
            app.logger.info(f'Message added to priority {priority_id} by admin {g.user.username}')

        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Error adding message to priority {priority_id}: {str(e)}')
            flash('Error adding message', 'error')

        return redirect(url_for('admin_panel'))

    @app.route('/delete_priority', methods=['POST'])
    @admin_required
    def delete_priority():
        priority_id = request.form.get('priority_id')

        if not priority_id:
            flash('Invalid priority ID', 'error')
            return redirect(url_for('admin_panel'))

        try:
            priority = Priority.query.get_or_404(priority_id)
            ticket_number = priority.bugzilla_ticket

            db.session.delete(priority)
            db.session.commit()

            flash(f'Priority {ticket_number} (ID: {priority_id}) deleted successfully', 'success')
            app.logger.info(f'Priority {priority_id} deleted by admin {g.user.username}')

        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Error deleting priority {priority_id}: {str(e)}')
            flash('Error deleting priority', 'error')

        return redirect(url_for('admin_panel'))

    def send_priority_emails_async(priority, mail, app):
        """Send priority emails asynchronously"""
        try:
            # Admin email
            admin_msg = Message(
                subject=f'New GPU Priority Request - {priority.bugzilla_ticket}',
                recipients=[app.config['ADMIN_EMAIL']],
                html=render_template('emails/admin_notification.html', priority=priority)
            )
            send_email_async(mail, admin_msg, app, priority.id)

            # User confirmation email
            user_msg = Message(
                subject=f'GPU Priority Submitted - {priority.bugzilla_ticket}',
                recipients=[priority.user.email],
                html=render_template('emails/user_confirmation.html', priority=priority)
            )
            send_email_async(mail, user_msg, app, priority.id)

        except Exception as e:
            app.logger.error(f'Failed to prepare emails for priority {priority.id}: {str(e)}')

    def send_status_update_email_async(priority, old_status, mail, app):
        """Send status update email asynchronously"""
        try:
            user_msg = Message(
                subject=f'GPU Priority Status Update - {priority.bugzilla_ticket}',
                recipients=[priority.user.email],
                html=render_template('emails/status_update.html', priority=priority, old_status=old_status)
            )
            send_email_async(mail, user_msg, app, priority.id)

        except Exception as e:
            app.logger.error(f'Failed to prepare status update email for priority {priority.id}: {str(e)}')

    # Error handlers
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.error(f'Internal server error: {str(error)}')
        flash('An internal error occurred. Please try again.', 'error')
        return redirect(url_for('index'))

    @app.errorhandler(502)
    def bad_gateway(error):
        db.session.rollback()
        app.logger.error(f'Bad gateway error: {str(error)}')
        flash('Service temporarily unavailable. Please try again.', 'error')
        return redirect(url_for('index'))

    return app

# Create the app instance
app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0')
