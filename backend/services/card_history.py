"""Published data stays stable while the editable preview row changes."""
from copy import deepcopy
from backend.models.card_history import CardHistory
from backend.models.preview_variant import PreviewVariant

FIELDS = ('title','description','type','image_url','composited_image_url','highlight_image_url',
          'render_spec','layout','platform_images','generation_mode','ai_reasoning','ignore_site_branding')
VARIANT_FIELDS = ('variant_key','title','description','subtitle','image_url','angle','tone','keywords')


def snapshot(preview):
    return {**{key: deepcopy(getattr(preview,key)) for key in FIELDS},
            'variants': [{key: getattr(v,key) for key in VARIANT_FIELDS} for v in preview.variants]}


def begin_edit(db, preview):
    # Capture legacy records before the first draft edit. Never replace an existing published snapshot.
    if preview.published_snapshot is None:
        preview.published_snapshot = snapshot(preview)
    if not db.query(CardHistory).filter_by(preview_id=preview.id, revision=preview.revision).first():
        db.add(CardHistory(preview_id=preview.id, revision=preview.revision, snapshot=snapshot(preview)))
    preview.auto_publish = False


def record_revision(db, preview):
    data = snapshot(preview)
    if preview.auto_publish:
        preview.published_snapshot = deepcopy(data)
    db.flush()
    if not db.query(CardHistory).filter_by(preview_id=preview.id, revision=preview.revision).first():
        db.add(CardHistory(preview_id=preview.id, revision=preview.revision, snapshot=data))


def restore_snapshot(preview, data):
    for key in FIELDS:
        setattr(preview, key, deepcopy(data.get(key)))
    preview.variants.clear()
    for item in data.get('variants', []):
        preview.variants.append(PreviewVariant(**{key: item.get(key) for key in VARIANT_FIELDS}))
