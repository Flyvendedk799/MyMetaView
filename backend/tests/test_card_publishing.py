from unittest.mock import patch
from backend.tests.test_platform_flows import client, _signup, _session
from backend.models.preview import Preview
from backend.models.domain import Domain


def seed(client):
    token, org_id = _signup(client, 'publisher@example.com')
    db=_session()
    db.add(Domain(name='cards.test',status='verified',organization_id=org_id))
    preview=Preview(url='https://cards.test/',domain='cards.test',title='Live',description='Live copy',
        type='landing',image_url='https://cdn.test/live.png',organization_id=org_id,
        render_spec={'composition':{'layout':'typographic'},'subtitle':'Live copy'})
    db.add(preview); db.commit(); pid=preview.id; db.close()
    return pid, {'Authorization':f'Bearer {token}'}


def served(client):
    return client.get('/api/v1/public/preview',params={'full_url':'https://cards.test/'},headers={'User-Agent':'Twitterbot/1.0'}).json()['title']


def test_draft_publish_restore_and_stale_save(client):
    pid,headers=seed(client)
    state=client.get(f'/api/v1/previews/{pid}/studio',headers=headers).json()
    original_revision=state['revision']
    with patch('backend.services.card_revision.rerender_card',return_value=('https://cdn.test/new.png','typographic')):
        response=client.put(f'/api/v1/previews/{pid}/studio',headers=headers,json={**state,'title':'Draft'})
    assert response.status_code==200,response.text
    draft=response.json()
    assert draft['has_draft']
    assert served(client)=='Live'
    stale=client.post(f'/api/v1/previews/{pid}/publish',headers=headers,json={'revision':original_revision})
    assert stale.status_code==409
    result=client.post(f'/api/v1/previews/{pid}/publish',headers=headers,json={'revision':draft['revision']})
    assert result.status_code==200,result.text
    assert served(client)=='Draft'
    history=client.get(f'/api/v1/previews/{pid}/history',headers=headers).json()
    assert any(r['title']=='Live' for r in history)
    restored=client.post(f'/api/v1/previews/{pid}/restore/{original_revision}',headers=headers,json={'revision':result.json()['revision']})
    assert restored.status_code==200,restored.text
    assert restored.json()['title']=='Live'
    assert served(client)=='Draft'


def test_failed_render_does_not_save_copy(client):
    pid,headers=seed(client)
    with patch('backend.services.card_revision.rerender_card',return_value=(None,None)):
        response=client.put(f'/api/v1/previews/{pid}',headers=headers,json={'title':'Broken'})
    assert response.status_code==502
    assert served(client)=='Live'
    state=client.get(f'/api/v1/previews/{pid}/studio',headers=headers).json()
    assert state['title']=='Live'


def test_optimistic_write_rejects_background_overwrite(client):
    from sqlalchemy.orm import sessionmaker
    from backend.services.card_revision import commit_card
    from fastapi import HTTPException
    import pytest
    pid,headers=seed(client)
    db=_session()
    another=sessionmaker(bind=db.bind)()
    stale=db.get(Preview,pid)
    newest=another.get(Preview,pid)
    newest.title='Newer edit';commit_card(another)
    stale.title='Old background render'
    with pytest.raises(HTTPException) as failure:commit_card(db)
    assert failure.value.status_code==409
    db.expire_all();assert db.get(Preview,pid).title=='Newer edit'
    another.close();db.close()
