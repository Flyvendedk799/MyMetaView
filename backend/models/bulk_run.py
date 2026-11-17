from datetime import datetime
from sqlalchemy import Column,Integer,String,Boolean,DateTime,ForeignKey,UniqueConstraint
from sqlalchemy.orm import relationship
from backend.db import Base

class BulkRun(Base):
    __tablename__='bulk_runs'
    id=Column(String,primary_key=True)
    organization_id=Column(Integer,ForeignKey('organizations.id'),nullable=False,index=True)
    user_id=Column(Integer,ForeignKey('users.id'),nullable=False)
    domain=Column(String,nullable=False)
    status=Column(String,nullable=False,default='running')
    force=Column(Boolean,nullable=False,default=False)
    ignore_branding=Column(Boolean,nullable=False,default=False)
    created_at=Column(DateTime,nullable=False,default=datetime.utcnow)
    items=relationship('BulkRunItem',cascade='all, delete-orphan',back_populates='run')

class BulkRunItem(Base):
    __tablename__='bulk_run_items'
    id=Column(Integer,primary_key=True)
    run_id=Column(String,ForeignKey('bulk_runs.id'),nullable=False,index=True)
    url=Column(String,nullable=False)
    status=Column(String,nullable=False,default='pending')
    attempts=Column(Integer,nullable=False,default=0)
    lease=Column(String)
    updated_at=Column(DateTime,nullable=False,default=datetime.utcnow)
    preview_id=Column(Integer,ForeignKey('previews.id',ondelete='SET NULL'))
    error=Column(String)
    run=relationship('BulkRun',back_populates='items')
    __table_args__=(UniqueConstraint('run_id','url',name='uq_bulk_run_url'),)
