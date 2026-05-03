from datetime import datetime
from . import db
from flask_login import UserMixin


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="client")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    events = db.relationship("Event", backref="user", lazy=True)


class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    title = db.Column(db.String(255), nullable=False)  # ex: "Mon mariage"
    event_datetime = db.Column(db.DateTime, nullable=False)

    location_name = db.Column(db.String(255), nullable=False)
    address = db.Column(db.String(255), nullable=False)

    # sections (MVP: on garde)
    show_location = db.Column(db.Boolean, default=True)
    show_program = db.Column(db.Boolean, default=False)
    show_contacts = db.Column(db.Boolean, default=False)
    show_instructions = db.Column(db.Boolean, default=False)

    instructions = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    guests = db.relationship("Guest", backref="event", lazy=True, cascade="all, delete-orphan")
    invitations = db.relationship("Invitation", backref="event", lazy=True, cascade="all, delete-orphan")

class Guest(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    event_id = db.Column(db.Integer, db.ForeignKey("event.id"), nullable=False)

    # ✅ Nouveau champ civilité
    # Valeurs attendues: MR, MME, MLLE, COUPLE
    civility = db.Column(db.String(10), nullable=False, default="MME")

    full_name = db.Column(db.String(255), nullable=False)

    # single / couple / family
    guest_type = db.Column(db.String(20), nullable=False)

    # taille du groupe
    party_size = db.Column(db.Integer, nullable=False, default=1)

    table_name = db.Column(db.String(50), nullable=True)

    phone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # relations
    invitation = db.relationship("Invitation", backref="guest", uselist=False)

class Invitation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("event.id"), nullable=False)
    guest_id = db.Column(db.Integer, db.ForeignKey("guest.id"), nullable=False)

    invitation_code = db.Column(db.String(80), unique=True, nullable=False, index=True)

    pdf_path = db.Column(db.String(500), nullable=True)
    qr_path = db.Column(db.String(500), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    rsvp = db.relationship("RSVP", backref="invitation", uselist=False, cascade="all, delete-orphan")


class RSVP(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invitation_id = db.Column(db.Integer, db.ForeignKey("invitation.id"), nullable=False, unique=True)

    # yes / no
    status = db.Column(db.String(10), nullable=False, default="pending")
    message = db.Column(db.Text, nullable=True)

    responded_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
