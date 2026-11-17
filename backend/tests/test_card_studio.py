from types import SimpleNamespace
from backend.services.card_studio import StudioEdit, studio_spec, preserve_locked_fields
import pytest
from pydantic import ValidationError

def test_locked_copy_and_assets_survive_generation():
    old={'composition':{'layout':'split','focal_x':23},'visual_url':'original','locks':['title','visual']}
    preview=SimpleNamespace(title='Approved',description='Original',render_spec=old)
    title,description,spec=preserve_locked_fields(preview,'Generated','Fresh',{'composition':{'layout':'product'},'visual_url':'new'})
    assert title=='Approved' and description=='Fresh'
    assert spec['visual_url']=='original' and spec['composition']['focal_x']==23
    assert spec['composition']['layout']=='product'

def test_studio_rejects_invalid_focal_point_and_layout():
    with pytest.raises(ValidationError): StudioEdit(revision=1,title='Test',focal_x=101)
    with pytest.raises(ValidationError): StudioEdit(revision=1,title='Test',layout='invented')

def test_spec_does_not_mutate_existing():
    original={'composition':{'layout':'split'}}
    spec=studio_spec(original,StudioEdit(revision=1,title='Test',layout='product'))
    assert original['composition']['layout']=='split'
    assert spec['composition']['layout']=='product'
