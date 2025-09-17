from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from sqlalchemy import Index, text

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    oidc_sub = db.Column(db.String(255), unique=True, nullable=False, index=True)
    username = db.Column(db.String(100), nullable=False, index=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    priorities = db.relationship('Priority', backref='user', lazy='dynamic', 
                               cascade='all, delete-orphan')

    # Indexes for performance
    __table_args__ = (
        Index('idx_user_oidc_username', 'oidc_sub', 'username'),
        Index('idx_user_email_created', 'email', 'created_at'),
    )

    def __repr__(self):
        return f'<User {self.username}>'

class AdminUser(db.Model):
    __tablename__ = 'admin_users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f'<AdminUser {self.username}>'

class Priority(db.Model):
    __tablename__ = 'priorities'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    bugzilla_ticket = db.Column(db.String(50), nullable=False, index=True)
    additional_usernames = db.Column(db.Text)
    slurm_project = db.Column(db.String(100), nullable=False, index=True)
    gpu_type = db.Column(db.String(50), nullable=False, index=True)
    gpu_count = db.Column(db.Integer, nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)
    admin_message = db.Column(db.Text)
    priority_name = db.Column(db.String(100), index=True)  # Admin-set priority name for SLURM
    status_updated_at = db.Column(db.DateTime, index=True)
    status_updated_by = db.Column(db.String(100))
    slurm_command = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Composite indexes for common queries
    __table_args__ = (
        Index('idx_priority_user_status', 'user_id', 'status'),
        Index('idx_priority_status_created', 'status', 'created_at'),
        Index('idx_priority_bugzilla_unique', 'bugzilla_ticket'),  # Prevent duplicate tickets
        Index('idx_priority_gpu_type_status', 'gpu_type', 'status'),
        Index('idx_priority_status_updated', 'status', 'status_updated_at'),
        db.UniqueConstraint('bugzilla_ticket', name='uq_priority_bugzilla_ticket'),
    )

    def __repr__(self):
        return f'<Priority {self.id}: {self.bugzilla_ticket}>'

    @property
    def additional_usernames_list(self):
        """Get list of additional usernames"""
        if self.additional_usernames:
            return [username.strip() for username in self.additional_usernames.split('\n') if username.strip()]
        return []

    @property
    def duration_display(self):
        """Display duration in human readable format"""
        days = self.duration_days
        if days == 1:
            return '1 Day'
        else:
            return f'{days} Days'

    @property
    def valid_until(self):
        """Calculate the expiration date for accepted priorities"""
        if self.status == 'accepted' and self.status_updated_at:
            return self.status_updated_at + timedelta(days=self.duration_days)
        return None

    @property
    def is_expired(self):
        """Check if the priority has expired"""
        if self.valid_until:
            return datetime.utcnow() > self.valid_until
        return False

    @property
    def is_archived(self):
        """Check if the priority should be archived (expired for more than 7 days)"""
        if self.valid_until:
            archive_cutoff = self.valid_until + timedelta(days=7)
            return datetime.utcnow() > archive_cutoff
        return False

# Database initialization and migration helpers
def init_db(app):
    """Initialize database with error handling"""
    with app.app_context():
        try:
            # Create all tables
            db.create_all()

            # Verify tables were created
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()

            if 'users' in tables and 'priorities' in tables and 'admin_users' in tables:
                print("✅ Database tables created successfully")
                return True
            else:
                print("❌ Failed to create all required tables")
                return False

        except Exception as e:
            print(f"❌ Database initialization error: {str(e)}")
            return False

def check_db_health(app):
    """Check database connection and health"""
    with app.app_context():
        try:
            # Test basic query
            result = db.session.execute(text('SELECT 1')).scalar()
            if result == 1:
                print("✅ Database connection healthy")
                return True
            else:
                print("❌ Database query failed")
                return False
        except Exception as e:
            print(f"❌ Database health check failed: {str(e)}")
            return False
