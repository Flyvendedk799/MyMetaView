"""One database record per URL; RQ is transport, not the progress ledger."""
from datetime import datetime,timedelta
from uuid import uuid4
from backend.models.bulk_run import BulkRun,BulkRunItem
from backend.models.preview import Preview
from backend.db.session import SessionLocal


def create_run(db,run_id,user_id,org_id,domain,urls,force=False,ignore_branding=False):
    existing=db.get(BulkRun,run_id)
    if existing:return existing
    run=BulkRun(id=run_id,user_id=user_id,organization_id=org_id,domain=domain,force=force,
                ignore_branding=ignore_branding,status='running')
    run.items=[BulkRunItem(url=url,status='pending') for url in dict.fromkeys(urls)]
    db.add(run);db.commit();return run


def summary(db,run,details=False):
    items=db.query(BulkRunItem).filter_by(run_id=run.id).order_by(BulkRunItem.id).all()
    completed=sum(i.status=='finished' for i in items);failed=sum(i.status=='failed' for i in items)
    result=dict(batch_id=run.id,status=run.status,domain=run.domain,total=len(items),completed=completed,
                failed=failed,created_at=run.created_at.isoformat(),kind='bulk',durable=True)
    if details:
        previews={p.id:p for p in db.query(Preview).filter(Preview.id.in_([i.preview_id for i in items if i.preview_id])).all()}
        result['results']=[dict(url=i.url,status=i.status,preview_id=i.preview_id,error=i.error,
            title=previews[i.preview_id].title if i.preview_id in previews else None,
            image_url=previews[i.preview_id].image_url if i.preview_id in previews else None) for i in items]
    return result


def dispatch(run_id):
    from rq import Queue
    from backend.queue.queue_connection import get_rq_redis_connection
    db=SessionLocal()
    try:
        run=db.get(BulkRun,run_id)
        if not run or run.status!='running':return
        queue=Queue('bulk_generation',connection=get_rq_redis_connection())
        for item in db.query(BulkRunItem).filter_by(run_id=run_id,status='pending').limit(100).all():
            now=datetime.utcnow()
            if not db.query(BulkRunItem).filter_by(id=item.id,status='pending').update({'status':'queued','updated_at':now},synchronize_session=False):continue
            db.commit()
            try:queue.enqueue(process_item,item.id,job_timeout=600)
            except Exception:
                db.query(BulkRunItem).filter_by(id=item.id,status='queued').update({'status':'pending','error':'Queue unavailable; the supervisor will retry dispatch.'},synchronize_session=False);db.commit()
                raise
    finally:db.close()


def finish_run(db,run):
    statuses=[s[0] for s in db.query(BulkRunItem.status).filter_by(run_id=run.id).all()]
    if run.status=='running' and statuses and all(s in ('finished','failed','cancelled') for s in statuses):
        outcome='completed' if all(s=='finished' for s in statuses) else ('partial' if 'finished' in statuses else 'failed')
        changed=db.query(BulkRun).filter_by(id=run.id,status='running').update({'status':outcome},synchronize_session=False)
        db.commit();db.refresh(run)
        if changed:
            # Retain the existing completion notification, once per completed attempt.
            try:
                from backend.models.user import User
                from backend.services.email_service import send_bulk_run_finished_email
                from backend.core.config import settings
                owner=db.get(User,run.user_id)
                if owner and owner.email:
                    send_bulk_run_finished_email(owner.email,run.domain,statuses.count('finished'),statuses.count('failed'),
                                                 f"{settings.FRONTEND_URL.rstrip('/')}/app/previews")
            except Exception:
                import logging
                logging.getLogger(__name__).warning('Bulk completion notification failed',exc_info=True)


def process_item(item_id):
    db=SessionLocal();lease=str(uuid4())
    try:
        item=db.get(BulkRunItem,item_id)
        if not item:return
        run=db.get(BulkRun,item.run_id)
        if run.status!='running':return
        claimed=db.query(BulkRunItem).filter(BulkRunItem.id==item_id,BulkRunItem.status.in_(['queued','pending'])).update(
            {'status':'running','lease':lease,'attempts':BulkRunItem.attempts+1,'updated_at':datetime.utcnow()},synchronize_session=False)
        db.commit()
        if not claimed:return
        try:
            from backend.jobs.preview_pipeline import generate_preview_job
            result=generate_preview_job(run.user_id,run.organization_id,item.url,run.domain,force_regenerate=run.force,
                                        ignore_site_branding=run.ignore_branding,allow_automatic_retry=False)
            values={'status':'finished','preview_id':result['preview_id'],'error':None}
        except Exception as exc:
            values={'status':'failed','error':str(exc)[:500]}
        # A recovered worker cannot overwrite the result of a newer attempt.
        db.query(BulkRunItem).filter_by(id=item_id,lease=lease).update({**values,'updated_at':datetime.utcnow()},synchronize_session=False)
        db.commit();db.refresh(run);finish_run(db,run)
    finally:db.close()


def control(db,run,action):
    if action=='pause' and run.status=='running':run.status='paused'
    elif action=='cancel':
        run.status='cancelled'
        db.query(BulkRunItem).filter(BulkRunItem.run_id==run.id,BulkRunItem.status.in_(['pending','queued'])).update({'status':'cancelled'},synchronize_session=False)
    elif action=='resume' and run.status=='paused':
        run.status='running'
        db.query(BulkRunItem).filter_by(run_id=run.id,status='queued').update({'status':'pending'},synchronize_session=False)
    elif action=='retry_failed' and run.status in ('failed','partial','completed'):
        run.status='running'
        db.query(BulkRunItem).filter_by(run_id=run.id,status='failed').update({'status':'pending','error':None,'attempts':0},synchronize_session=False)
    else:raise ValueError('This action is not available for the current run state.')
    db.commit()
    return summary(db,run,True)


def recover_runs():
    db=SessionLocal()
    try:
        cutoff=datetime.utcnow()-timedelta(minutes=15)
        rows=db.query(BulkRunItem).join(BulkRun).filter(BulkRun.status=='running',BulkRunItem.status.in_(['running','queued']),BulkRunItem.updated_at<cutoff).all()
        for row in rows:
            row.status='pending' if row.attempts<3 else 'failed'
            row.error='Worker stopped before completing this URL.';row.lease=None
        db.commit()
        for run in db.query(BulkRun).filter_by(status='running').all():
            finish_run(db,run)
            if run.status=='running':dispatch(run.id)
    finally:db.close()
