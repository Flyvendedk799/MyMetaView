from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from backend.db.session import get_db
from backend.core.deps import get_current_org, role_required
from backend.models.organization_member import OrganizationRole
from backend.models.organization import Organization
from backend.models.domain import Domain
from backend.models.site_coverage import SiteRefreshPolicy, SitePageCoverage
from backend.jobs.site_refresh import queue_scan

router=APIRouter(prefix='/coverage',tags=['coverage'])
editor=role_required([OrganizationRole.OWNER,OrganizationRole.ADMIN,OrganizationRole.EDITOR])

def domain_for(db,org,domain_id):
    domain=db.query(Domain).filter_by(id=domain_id,organization_id=org.id).first()
    if not domain: raise HTTPException(404,'Domain not found')
    return domain

def policy_for(db,domain_id):
    policy=db.get(SiteRefreshPolicy,domain_id)
    if not policy:
        policy=SiteRefreshPolicy(domain_id=domain_id,enabled=False,interval_hours=24,next_scan_at=datetime.utcnow())
        db.add(policy);db.commit()
    return policy

@router.get('/{domain_id}')
def coverage(domain_id:int,db:Session=Depends(get_db),org:Organization=Depends(get_current_org)):
    domain_for(db,org,domain_id)
    policy=db.get(SiteRefreshPolicy,domain_id)
    rows=db.query(SitePageCoverage).filter_by(domain_id=domain_id).order_by(SitePageCoverage.url).limit(2000).all()
    return {'enabled':bool(policy and policy.enabled),'interval_hours':policy.interval_hours if policy else 24,
            'last_scan_at':policy.last_scan_at if policy else None,'error':policy.last_error if policy else None,
            'pages':[{'id':r.id,'url':r.url,'canonical_url':r.canonical_url,'state':r.state,'error':r.error,
                      'checked_at':r.checked_at,'generated_at':r.generated_at} for r in rows]}

class RefreshSettings(BaseModel):
    enabled:bool
    interval_hours:int=Field(24,ge=6,le=168)

@router.put('/{domain_id}')
def settings(domain_id:int,body:RefreshSettings,db:Session=Depends(get_db),org:Organization=Depends(get_current_org),role=Depends(editor)):
    domain=domain_for(db,org,domain_id)
    if body.enabled and domain.status!='verified': raise HTTPException(409,'Verify this domain first.')
    policy=policy_for(db,domain_id);policy.enabled=body.enabled;policy.interval_hours=body.interval_hours;policy.next_scan_at=datetime.utcnow();db.commit()
    return {'enabled':policy.enabled,'interval_hours':policy.interval_hours}

@router.post('/{domain_id}/scan',status_code=202)
def scan(domain_id:int,db:Session=Depends(get_db),org:Organization=Depends(get_current_org),role=Depends(editor)):
    domain=domain_for(db,org,domain_id)
    if domain.status!='verified':raise HTTPException(409,'Verify this domain first.')
    policy_for(db,domain_id)
    try: job=queue_scan(domain_id)
    except Exception as exc:raise HTTPException(503,'Could not queue scan. Try again shortly.') from exc
    return {'job_id':job.id}
