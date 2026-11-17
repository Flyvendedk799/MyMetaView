from backend.services.site_coverage import page_identity,page_observation

def test_identity_keeps_case_and_product_options():
    assert page_identity('https://Shop.test/Case?variant=Red&utm_source=x#foo')=='https://shop.test/Case?variant=Red'
    assert page_identity('https://shop.test/Case?variant=Red')!=page_identity('https://shop.test/case?variant=Blue')

def test_content_hash_ignores_navigation_but_not_product_facts():
    a=page_observation('<nav>Today</nav><h1>Chair</h1><p>200 DKK</p>','https://shop.test/chair','shop.test')
    b=page_observation('<nav>Tomorrow</nav><h1>Chair</h1><p>200 DKK</p>','https://shop.test/chair','shop.test')
    c=page_observation('<h1>Chair</h1><p>300 DKK</p>','https://shop.test/chair','shop.test')
    assert a==b and a[1]!=c[1]

def test_cross_site_canonical_does_not_transfer_identity():
    canonical,_=page_observation('<link rel="canonical" href="https://other.test/page"><h1>Hello</h1>','https://shop.test/page','shop.test')
    assert canonical=='https://shop.test/page'
