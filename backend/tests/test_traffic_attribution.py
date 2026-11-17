from backend.services.traffic_attribution import social_visit_attribution

def test_bot_fetch_is_not_a_referred_visit():
    assert social_visit_attribution('https://example.com','https://facebook.com','facebookexternalhit') is None

def test_missing_referrer_is_not_inferred_from_utm():
    assert social_visit_attribution('https://example.com?utm_campaign=launch',None,'Chrome') is None

def test_explicit_campaign_and_variant_labels_are_retained():
    result=social_visit_attribution('https://example.com?utm_campaign=launch&mmv_variant=b','https://www.linkedin.com/feed','Chrome')
    assert result=={'event_source':'social_referral','campaign':'launch','variant':'b'}

def test_lookalike_referrer_is_not_a_social_network():
    assert social_visit_attribution('https://example.com','https://linkedin.com.example.org','Chrome') is None
