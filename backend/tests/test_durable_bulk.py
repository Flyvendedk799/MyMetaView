from datetime import datetime,timedelta
from unittest.mock import patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.db import Base
import backend.models
from backend.services.bulk_runs import create_run,control,summary,process_item,recover_runs
from backend.models.bulk_run import BulkRunItem

@pytest.fixture
def sessions():
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine)
    factory=sessionmaker(bind=engine,expire_on_commit=False)
    yield factory
    engine.dispose()


def test_pause_resume_and_retry_only_failed_preserve_successes(sessions):
    db=sessions();run=create_run(db,'run',1,1,'test',['https://test/a','https://test/b'])
    run.items[0].status='finished';run.items[1].status='failed';db.commit()
    control(db,run,'pause');assert run.status=='paused'
    control(db,run,'resume');assert run.status=='running'
    run.status='partial';db.commit()
    control(db,run,'retry_failed');db.expire_all()
    assert [i.status for i in db.get(type(run),'run').items]==['finished','pending']
    assert summary(db,run)['completed']==1


def test_duplicate_delivery_generates_once(sessions):
    db=sessions();run=create_run(db,'run',1,1,'test',['https://test/a']);item_id=run.items[0].id
    with patch('backend.services.bulk_runs.SessionLocal',sessions),patch('backend.jobs.preview_pipeline.generate_preview_job',return_value={'preview_id':9}) as generate:
        process_item(item_id);process_item(item_id)
    assert generate.call_count==1
    db.expire_all();assert db.get(BulkRunItem,item_id).status=='finished'


def test_worker_restart_requeues_without_touching_finished_items(sessions):
    db=sessions();run=create_run(db,'run',1,1,'test',['https://test/a','https://test/b'])
    run.items[0].status='finished';run.items[1].status='running';run.items[1].attempts=1;run.items[1].updated_at=datetime.utcnow()-timedelta(hours=1);db.commit()
    with patch('backend.services.bulk_runs.SessionLocal',sessions),patch('backend.services.bulk_runs.dispatch') as dispatch:
        recover_runs()
    db.expire_all();assert [i.status for i in db.get(type(run),'run').items]==['finished','pending']
    dispatch.assert_called_once_with('run')


def test_cancel_keeps_inflight_and_completed_pages(sessions):
    db=sessions();run=create_run(db,'run',1,1,'test',['https://test/a','https://test/b'])
    run.items[0].status='running';db.commit();control(db,run,'cancel');db.expire_all()
    assert [i.status for i in db.get(type(run),'run').items]==['running','cancelled']
