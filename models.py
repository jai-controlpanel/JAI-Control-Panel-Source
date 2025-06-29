from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta, timezone # <<< ADD timezone here
import uuid

# Create the database instance, but don't associate it with an app yet.
db = SQLAlchemy()

class User(db.Model):
    """Represents a registered user for the control panel."""
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True) # <<< FIX: Allow NULL email
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_trial = db.Column(db.Boolean, default=False, nullable=False)

    def __repr__(self):
        return f'<User {self.username}>'

class ActivationCode(db.Model):
    """Represents a single-use activation code for registration."""
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False)
    is_used = db.Column(db.Boolean, default=False, nullable=False)

    def __repr__(self):
        return f'<Code {self.code}>'

class TrialKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    activation_time = db.Column(db.DateTime(timezone=True), nullable=True)
    expiry_time = db.Column(db.DateTime(timezone=True), nullable=True)
    activated_by_user_id = db.Column(db.String(100), nullable=True)
    duration_hours = db.Column(db.Float, default=0.05) # TEMPORARY: Set for quick testing (e.g., 0.05 for 3 minutes)

    def activate(self, user_id):
        if self.is_active:
            self.is_active = False # Mark as used
            self.activated_by_user_id = user_id
            self.activation_time = datetime.now(timezone.utc) # <<< CRITICAL CHANGE HERE
            self.expiry_time = self.activation_time + timedelta(hours=self.duration_hours)
            return True
        return False

    def deactivate(self):
        self.is_active = False
    

class IpRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(80), db.ForeignKey('user.username'), nullable=False) 
    ip_address = db.Column(db.String(45), nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc)) 
    user_agent = db.Column(db.String(512), nullable=True)
    city = db.Column(db.String(100), nullable=True)      
    country = db.Column(db.String(100), nullable=True)    
    latitude = db.Column(db.Float, nullable=True)        
    longitude = db.Column(db.Float, nullable=True)

class ChatLogEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(128), nullable=False)
    message = db.Column(db.Text, nullable=False)
    platform = db.Column(db.String(64), nullable=False)
    sender = db.Column(db.String(64), nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False) # <<< CRITICAL CHANGE HERE

    def __repr__(self):
        return f"<ChatLogEntry {self.id} | User: {self.user_id} | Sender: {self.sender} | Platform: {self.platform} | Time: {self.timestamp}>"
    
class UserImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(80), db.ForeignKey('user.username'), nullable=False) # Links to the User model
    image_path = db.Column(db.String(255), unique=True, nullable=False) # Path relative to 'static/' folder
    label = db.Column(db.String(255), nullable=True) # User-provided label/description
    upload_timestamp = db.Column(db.DateTime, default=datetime.now(timezone.utc)) # When it was uploaded

    # Optional: Define relationship to the User model (for easier querying later)
    user = db.relationship('User', backref=db.backref('uploaded_images', lazy=True))

    def __repr__(self):
        return f'<UserImage {self.image_path} by {self.user_id} ({self.label})>'
    

