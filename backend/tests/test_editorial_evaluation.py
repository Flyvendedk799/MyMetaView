import pytest
from backend.services.preview.corpus.editorial import summarize_reviews

def review(**changes):
    return dict(url='https://example.com',revision='abc',reviewer='Editor',reviewed_at='2026-11-17',
        page_type='product',accuracy=5,relevance=4,brand_fidelity=4,small_size_readability=5,
        comparison='better',needs_edit=False,**changes)

def test_missing_human_reviews_cannot_pass():
    assert summarize_reviews([])['overall']['publishable_rate'] is None
    row=review();row['accuracy']=None
    with pytest.raises(ValueError): summarize_reviews([row])

def test_factually_wrong_card_fails_despite_beautiful_pixels():
    row=review();row['accuracy']=4
    result=summarize_reviews([row])
    assert result['overall']['publishable_rate']==0
    assert result['by_page_type']['product']['beats_original_rate']==1

def test_duplicate_review_does_not_inflate_results():
    with pytest.raises(ValueError): summarize_reviews([review(),review()])
