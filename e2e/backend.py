"""Local journey server. Production app plus deterministic external inputs.

Not imported by production. Run only on loopback with an isolated database/Redis.
"""
import os
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4
from html import escape
from pathlib import Path
import rq

if os.environ.get('JOURNEY_TEST_SERVER') != '1':
    raise RuntimeError('This fixture server requires JOURNEY_TEST_SERVER=1')
if os.environ.get('DATABASE_URL') != 'sqlite:///work/journey.db':
    raise RuntimeError('Journey tests require their isolated work/journey.db')
from urllib.parse import urlparse
import redis
redis_url = os.environ['REDIS_URL']
redis_target = urlparse(redis_url)
if redis_target.hostname not in ('localhost', '127.0.0.1') or redis_target.path != '/15':
    raise RuntimeError('Journey tests require a dedicated local Redis database 15')
# The database and Redis state both belong exclusively to this fixture server.
redis.Redis.from_url(redis_url).flushdb()
Path('work').mkdir(exist_ok=True)
Path('work/journey.db').unlink(missing_ok=True)
from backend.main import app
from backend.db import Base
from backend.db.session import engine, SessionLocal
from backend.models.domain import Domain
from backend.models.preview import Preview
from backend.services.preview_engine import PreviewEngineResult
from backend.services.manual_card import template_render_spec
from backend.services.card_rerender import rerender_card
from backend.services.preview.net.session import FetchResult
from backend.services.r2_client import read_stored_asset
from backend.jobs import preview_pipeline,site_refresh
from backend.services import share_delivery

Base.metadata.create_all(engine)
executor=ThreadPoolExecutor(max_workers=2)
source={'title':'A useful page','description':'A clear description from the source page.'}
failures=set()

class FixtureEngine:
    def __init__(self,config):self.config=config
    def generate(self,url,**kwargs):
        if '/fails' in url and url not in failures:
            failures.add(url);raise RuntimeError('Fixture transient render failure')
        spec=template_render_spec(title=source['title'],description=source['description'],domain='journey.test')
        image,layout=rerender_card(spec,url=url,title=source['title'],subtitle=source['description'])
        if not image:raise RuntimeError('Real renderer failed in journey fixture')
        return PreviewEngineResult(url=url,title=source['title'],description=source['description'],
            composited_preview_image_url=image,render_spec=spec,rendered_layout=layout,
            blueprint={'template_type':'landing'},message='Fixture page; actual renderer')
preview_pipeline.PreviewEngine=FixtureEngine
preview_pipeline.enqueue_platform_renders=lambda *a,**kw:True

# Keep asynchronous completion and the real durable item/pipeline functions,
# without requiring separate worker processes in the browser test harness.
def enqueue(self,func,*args,**kwargs):
    for key in ('job_timeout','job_id','result_ttl','failure_ttl'):kwargs.pop(key,None)
    executor.submit(func,*args,**kwargs)
    return SimpleNamespace(id=str(uuid4()))
rq.Queue.enqueue=enqueue


def fixture_fetch(url,**kwargs):
    image=read_stored_asset(url)
    if image:return FetchResult(url,True,200,image,'image/png')
    if 'journey.test' not in url:return FetchResult(url,False,404)
    db=SessionLocal()
    try:
        preview=db.query(Preview).filter_by(url=url).first()
        published=(preview.published_snapshot or {}) if preview else {}
        title=published.get('title',preview.title if preview else source['title'])
        image_url=published.get('image_url',preview.image_url if preview else '')
        html=f'<html><head><meta property="og:title" content="{escape(title)}"><meta property="og:image" content="{escape(image_url)}"></head><body><h1>{escape(source["title"])}</h1><p>{escape(source["description"])}</p></body></html>'
        return FetchResult(url,True,200,html.encode(),'text/html')
    finally:db.close()
share_delivery.fetch=fixture_fetch
site_refresh.fetch=fixture_fetch
site_refresh.discover_sitemap_entries=lambda *a,**kw:[{'url':'https://journey.test/','lastmod':'2026-11-17'}]

@app.post('/__fixture/verify/{domain_id}')
def verify(domain_id:int):
    db=SessionLocal()
    try:
        domain=db.get(Domain,domain_id);domain.status='verified';db.commit()
        return {'verified':True}
    finally:db.close()

@app.post('/__fixture/source')
def update_source(body:dict):
    source.update(body)
    return source

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5174'],allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
