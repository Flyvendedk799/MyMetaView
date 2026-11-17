"""Recurring discovery, bounded scans and refresh jobs, supervised by the worker pool."""
from datetime import datetime, timedelta
from sqlalchemy import or_
from rq import Queue
from backend.db.session import SessionLocal
from backend.models.domain import Domain
from backend.models.organization import Organization
from backend.models.preview import Preview
from backend.models.site_coverage import SiteRefreshPolicy, SitePageCoverage
from backend.queue.queue_connection import get_rq_redis_connection
from backend.services.site_coverage import page_identity, page_observation
from backend.services.sitemap_discovery import discover_sitemap_entries
from backend.services.preview.net.session import fetch


def queue_scan(domain_id):
    return Queue('bulk_generation',connection=get_rq_redis_connection()).enqueue(scan_domain,domain_id,job_timeout=1800)


def enqueue_due_scans():
    db=SessionLocal()
    try:
        now=datetime.utcnow()
        due=db.query(SiteRefreshPolicy).filter(SiteRefreshPolicy.enabled.is_(True),SiteRefreshPolicy.next_scan_at<=now).all()
        for policy in due:
            # Conditional claim works across worker supervisors.
            claimed=db.query(SiteRefreshPolicy).filter_by(domain_id=policy.domain_id).filter(SiteRefreshPolicy.next_scan_at<=now).update(
                {'next_scan_at':now+timedelta(hours=policy.interval_hours)},synchronize_session=False)
            db.commit()
            if claimed:
                try: queue_scan(policy.domain_id)
                except Exception as exc:
                    policy.next_scan_at=now+timedelta(minutes=5);policy.last_error=str(exc)[:400];db.commit()
    finally: db.close()


def scan_domain(domain_id):
    db=SessionLocal()
    try:
        domain=db.get(Domain,domain_id)
        if not domain or domain.status!='verified': return
        policy=db.get(SiteRefreshPolicy,domain_id)
        entries=discover_sitemap_entries(domain.name,max_urls=2000)
        # Existing inventory is also checked: a 404/410 is explicit removal evidence.
        known=[{'url':r.url,'lastmod':r.sitemap_lastmod} for r in db.query(SitePageCoverage).filter_by(domain_id=domain_id).all()]
        entries=list({page_identity(e['url']):e for e in known+entries}.values())
        queue=Queue('bulk_generation',connection=get_rq_redis_connection())
        for entry in entries:
            url=page_identity(entry['url'])
            row=db.query(SitePageCoverage).filter_by(domain_id=domain_id,url=url).first()
            if row is None:
                row=SitePageCoverage(domain_id=domain_id,url=url,state='missing');db.add(row);db.flush()
            row.sitemap_lastmod=entry.get('lastmod');db.commit()
            queue.enqueue(inspect_page,row.id,job_timeout=120)
        if policy:
            policy.last_scan_at=datetime.utcnow()
            policy.last_error=None if entries else 'No URLs discovered. Add a sitemap or generate a card first.'
            db.commit()
    except Exception as exc:
        db.rollback()
        policy=db.get(SiteRefreshPolicy,domain_id)
        if policy: policy.last_error=str(exc)[:400];db.commit()
        raise
    finally: db.close()


def inspect_page(page_id):
    db=SessionLocal()
    try:
        row=db.get(SitePageCoverage,page_id)
        if not row: return
        domain=db.get(Domain,row.domain_id)
        if not domain or domain.status!='verified': return
        policy=db.get(SiteRefreshPolicy,row.domain_id)
        page=fetch(row.url,timeout=8,max_bytes=2*1024*1024)
        row.checked_at=datetime.utcnow()
        if page.status in (404,410):
            row.state='removed';row.error=None;db.commit();return
        if not page.ok:
            row.state='failed';row.error=page.error or 'Could not read page';db.commit();return
        canonical,fingerprint=page_observation(page.text,page.url,domain.name)
        row.canonical_url=canonical;row.fingerprint=fingerprint;row.error=None
        preview=db.query(Preview).filter_by(organization_id=domain.organization_id,url=canonical).first()
        if row.generated_fingerprint==fingerprint and preview:
            row.state='ready';db.commit();return
        row.state='stale' if preview else 'missing';db.commit()
        if policy and policy.enabled:
            row.state='queued';db.commit()
            try:
                Queue('bulk_generation',connection=get_rq_redis_connection()).enqueue(refresh_page,row.id,fingerprint,job_timeout=600)
            except Exception as exc:
                row.state='failed';row.error=str(exc)[:400];db.commit()
    finally: db.close()


def refresh_page(page_id, fingerprint):
    db=SessionLocal()
    try:
        row=db.get(SitePageCoverage,page_id)
        if not row or row.fingerprint!=fingerprint or row.generated_fingerprint==fingerprint: return
        domain=db.get(Domain,row.domain_id);policy=db.get(SiteRefreshPolicy,row.domain_id)
        if not domain or domain.status!='verified' or not policy or not policy.enabled:
            row.state='stale' if row.generated_fingerprint else 'missing';db.commit();return
        org=db.get(Organization,domain.organization_id)
        url=row.canonical_url or row.url
        preview=db.query(Preview).filter_by(organization_id=domain.organization_id,url=url).first()
        # Reuse the existing quota semantics for new cards; updates keep their slot.
        from backend.core.plans import plan_limit
        limit=plan_limit(org,'previews_month')
        start=datetime.utcnow().replace(day=1,hour=0,minute=0,second=0,microsecond=0)
        if not preview and limit is not None and db.query(Preview).filter(Preview.organization_id==org.id,Preview.created_at>=start).count()>=limit:
            row.state='failed';row.error='Monthly preview limit reached';db.commit();return
        row.state='generating';db.commit()
        from backend.jobs.preview_pipeline import generate_preview_job
        generate_preview_job(domain.user_id or org.owner_user_id,org.id,url,domain.name,force_regenerate=True,
                             ignore_site_branding=bool(preview and preview.ignore_site_branding))
        row.generated_fingerprint=fingerprint;row.generated_at=datetime.utcnow();row.state='ready';row.error=None;db.commit()
    except Exception as exc:
        db.rollback();row=db.get(SitePageCoverage,page_id)
        if row: row.state='failed';row.error=str(exc)[:400];db.commit()
        raise
    finally: db.close()
