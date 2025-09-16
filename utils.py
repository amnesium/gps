from models import User, AdminUser, db
import re
import subprocess
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
import logging

# Set up logger
logger = logging.getLogger(__name__)

def get_or_create_user(user_info):
    """Get or create user from OIDC user info with better error handling"""
    try:
        oidc_sub = user_info.get('sub')
        if not oidc_sub:
            logger.error('No OIDC sub found in user info')
            raise ValueError('Invalid OIDC user info: missing sub')

        # Try to get existing user first
        user = User.query.filter_by(oidc_sub=oidc_sub).first()

        if not user:
            # Create new user
            username = user_info.get('preferred_username')
            if not username:
                email = user_info.get('email', '')
                username = email.split('@') if '@' in email else 'user'

            user = User(
                oidc_sub=oidc_sub,
                username=username,
                email=user_info.get('email', ''),
                first_name=user_info.get('given_name', ''),
                last_name=user_info.get('family_name', '')
            )

            try:
                db.session.add(user)
                db.session.commit()
                logger.info(f'Created new user: {username}')
            except IntegrityError as e:
                db.session.rollback()
                # Handle case where user was created by another request
                user = User.query.filter_by(oidc_sub=oidc_sub).first()
                if not user:
                    logger.error(f'Failed to create user {username}: {str(e)}')
                    raise
                logger.info(f'User {username} already exists, using existing record')
        else:
            # Update user info if changed
            updated = False
            new_email = user_info.get('email', '')
            new_first_name = user_info.get('given_name', '')
            new_last_name = user_info.get('family_name', '')

            if user.email != new_email:
                user.email = new_email
                updated = True
            if user.first_name != new_first_name:
                user.first_name = new_first_name
                updated = True
            if user.last_name != new_last_name:
                user.last_name = new_last_name
                updated = True

            if updated:
                try:
                    user.updated_at = datetime.utcnow()
                    db.session.commit()
                    logger.info(f'Updated user info for: {user.username}')
                except SQLAlchemyError as e:
                    db.session.rollback()
                    logger.error(f'Failed to update user {user.username}: {str(e)}')
                    # Continue anyway with existing data

        return user

    except Exception as e:
        logger.error(f'Error in get_or_create_user: {str(e)}')
        db.session.rollback()
        raise

def is_admin_user(username):
    """Check if user is an admin with caching"""
    if not username:
        return False

    try:
        # Use exists() for better performance
        return db.session.query(
            AdminUser.query.filter_by(username=username).exists()
        ).scalar()
    except Exception as e:
        logger.error(f'Error checking admin status for {username}: {str(e)}')
        return False

def generate_slurm_command(priority):
    """Generate slurm command for GPU priority using admin-set priority name"""
    try:
        if not priority or not priority.priority_name:
            logger.warning(f'Cannot generate SLURM command: missing priority or priority_name')
            return None

        # Format QOS name according to: prio-<qos_name>-<duration>d
        base_qos_name = priority.priority_name
        qos_name = f"prio-{base_qos_name}-{priority.duration_days}d"

        # Get all users (primary + additional)
        all_users = [priority.user.username]
        if priority.additional_usernames_list:
            all_users.extend(priority.additional_usernames_list)

        commands = []

        # Add comment header
        commands.append(f"# GPU Priority Commands for Ticket: {priority.bugzilla_ticket}")
        commands.append(f"# Generated on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}")
        commands.append(f"# Base Priority Name: {base_qos_name}")
        commands.append(f"# QOS Name: {qos_name}")
        commands.append(f"# Users: {', '.join(all_users)}")
        commands.append("")

        # Create QOS
        commands.append("# Create QOS with resource limits")
        qos_cmd = (
            f"sacctmgr add qos {qos_name} "
            f"GrpTRES=gres/gpu:{priority.gpu_type}={priority.gpu_count} "
            f"MaxWall={priority.duration_days}-0 "
            f"Priority=1000"
        )
        commands.append(qos_cmd)

        commands.append("")
        commands.append("# Assign QOS to users")

        # Assign QOS to each user
        for username in all_users:
            user_cmd = (
                f"sacctmgr modify user {username} "
                f"set qos+={qos_name} "
                f"where account={priority.slurm_project}"
            )
            commands.append(user_cmd)

        # Calculate cleanup date from when priority was accepted
        if priority.status_updated_at:
            cleanup_date = priority.status_updated_at + timedelta(days=priority.duration_days)

            commands.append("")
            commands.append("# Schedule QOS cleanup")
            # Fixed at command - use proper syntax with -t flag for timestamp format
            cleanup_cmd = (
                f"echo 'sacctmgr -i delete qos {qos_name}' | "
                f"at -t {cleanup_date.strftime('%Y%m%d%H%M')}"
            )
            commands.append(cleanup_cmd)

        commands.append("")
        commands.append("# Verification commands")
        commands.append(f"sacctmgr show qos {qos_name}")
        commands.append(f"squeue -u {','.join(all_users)}")

        result = '\n'.join(commands)
        logger.info(f'Generated SLURM commands for priority {priority.id}')
        return result

    except Exception as e:
        logger.error(f'Error generating SLURM command for priority {priority.id if priority else "None"}: {str(e)}')
        return None

def validate_bugzilla_ticket(ticket):
    """Validate bugzilla ticket format - numbers only"""
    if not ticket or not isinstance(ticket, str):
        return False

    ticket = ticket.strip()
    if not ticket:
        return False

    try:
        # Only allow pure numbers (digits only)
        return ticket.isdigit() and len(ticket) <= 50 and len(ticket) >= 1
    except Exception as e:
        logger.error(f'Error validating Bugzilla ticket {ticket}: {str(e)}')
        return False

def validate_username(username):
    """Validate username format with better error handling"""
    if not username or not isinstance(username, str):
        return False

    username = username.strip()
    if not username:
        return False

    try:
        # Check each username if multiple (separated by newlines)
        usernames = [u.strip() for u in username.split('\n') if u.strip()]
        if not usernames:
            return False

        username_pattern = r'^[a-zA-Z][a-zA-Z0-9\.\-]*$'

        for user in usernames:
            if not re.match(username_pattern, user):
                return False
            if len(user) < 2 or len(user) > 50:
                return False

        return len(usernames) <= 10  # Reasonable limit

    except Exception as e:
        logger.error(f'Error validating username {username}: {str(e)}')
        return False

def validate_priority_name(priority_name):
    """Validate priority name for SLURM QOS with better error handling"""
    if not priority_name or not isinstance(priority_name, str):
        return False

    priority_name = priority_name.strip()
    if not priority_name:
        return False

    try:
        # SLURM QOS names should be alphanumeric with underscores and hyphens
        pattern = r'^[a-zA-Z0-9_-]+$'
        return (bool(re.match(pattern, priority_name)) and 
                len(priority_name) >= 2 and 
                len(priority_name) <= 50 and
                not priority_name.startswith('-') and  # Cannot start with dash
                not priority_name.endswith('-'))  # Cannot end with dash
    except Exception as e:
        logger.error(f'Error validating priority name {priority_name}: {str(e)}')
        return False