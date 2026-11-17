"""User-owned choices survive regeneration; model output fills unlocked fields."""
from copy import deepcopy
from typing import Literal, Optional
from pydantic import BaseModel, Field, HttpUrl
from backend.services.card_rerender import apply_direction

Lock = Literal['title', 'description', 'layout', 'visual', 'logo']

class StudioEdit(BaseModel):
    revision: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field('', max_length=500)
    visual_url: Optional[HttpUrl] = None
    logo_url: Optional[HttpUrl] = None
    layout: Literal['typographic','split','stat','profile','editorial','product'] = 'typographic'
    panel: Literal['primary','secondary','dark','light'] = 'primary'
    accent: Literal['bar','dot','shape'] = 'bar'
    focal_x: float = Field(50, ge=0, le=100)
    focal_y: float = Field(50, ge=0, le=100)
    locks: list[Lock] = Field(default_factory=list)


def studio_spec(original, edit):
    spec = apply_direction(deepcopy(original), layout=edit.layout, panel=edit.panel, accent=edit.accent)
    spec.update(visual_url=str(edit.visual_url) if edit.visual_url else None,
                logo_url=str(edit.logo_url) if edit.logo_url else None, locks=list(dict.fromkeys(edit.locks)))
    spec['composition'].update(focal_x=edit.focal_x, focal_y=edit.focal_y)
    return spec


def preserve_locked_fields(preview, title, description, proposed_spec):
    old = preview.render_spec or {}
    locks = old.get('locks', [])
    spec = deepcopy(proposed_spec or old)
    spec['locks'] = locks
    if 'title' in locks: title = preview.title
    if 'description' in locks: description = preview.description
    if 'layout' in locks: spec['composition'] = deepcopy(old.get('composition', {}))
    if 'visual' in locks:
        spec['visual_url'] = old.get('visual_url')
        for key in ('focal_x', 'focal_y'):
            spec.setdefault('composition', {})[key] = old.get('composition', {}).get(key, 50)
    if 'logo' in locks: spec['logo_url'] = old.get('logo_url')
    return title, description, spec
