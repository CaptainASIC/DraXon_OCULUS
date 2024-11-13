"""SQLAlchemy models for DraXon OCULUS v3"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class DraXonDivision(Base):
    """Division model"""
    __tablename__ = 'v3_divisions'

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    role_id = Column(Text)  # Discord role ID as text

class DraXonMember(Base):
    """Member model"""
    __tablename__ = 'v3_members'

    id = Column(Integer, primary_key=True)
    discord_id = Column(Text, unique=True, nullable=False)  # Discord ID as text
    rank = Column(String(3))  # MG, CR, EXE, TL, EMP, AP
    division_id = Column(Integer, ForeignKey('v3_divisions.id'))
    join_date = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(20), default='ACTIVE')

class DraXonPosition(Base):
    """Position model"""
    __tablename__ = 'v3_positions'

    id = Column(Integer, primary_key=True)
    title = Column(String(100), nullable=False)
    division_id = Column(Integer, ForeignKey('v3_divisions.id'), nullable=False)
    required_rank = Column(String(3), nullable=False)  # EXE, TL, EMP
    status = Column(String(20), default='OPEN')
    holder_id = Column(Integer, ForeignKey('v3_members.id'))

class DraXonApplication(Base):
    """Application model"""
    __tablename__ = 'v3_applications'

    id = Column(Integer, primary_key=True)
    applicant_id = Column(Integer, ForeignKey('v3_members.id'), nullable=False)
    position_id = Column(Integer, ForeignKey('v3_positions.id'), nullable=False)
    thread_id = Column(Text, nullable=False)  # Discord thread ID as text
    status = Column(String(20), default='PENDING')
    previous_experience = Column(Text)
    position_statement = Column(Text)
    additional_info = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class DraXonVote(Base):
    """Vote model"""
    __tablename__ = 'v3_votes'

    id = Column(Integer, primary_key=True)
    application_id = Column(Integer, ForeignKey('v3_applications.id'), nullable=False)
    voter_id = Column(Integer, ForeignKey('v3_members.id'), nullable=False)
    vote = Column(String(10), nullable=False)  # APPROVE or REJECT
    comment = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class DraXonAuditLog(Base):
    """Audit log model"""
    __tablename__ = 'v3_audit_logs'

    id = Column(Integer, primary_key=True)
    action_type = Column(String(50), nullable=False)
    actor_id = Column(Text, nullable=False)  # Discord ID as text
    target_id = Column(Text)  # Optional target Discord ID as text
    details = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
