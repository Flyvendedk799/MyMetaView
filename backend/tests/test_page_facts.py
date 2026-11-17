from backend.services.preview.extraction.page_facts import extract_page_facts, grounded_copy
from backend.services.preview.stages import ReasoningResult

def test_main_entity_selected_over_recommendation():
    facts=extract_page_facts('''<html lang="da"><h1>Stol</h1><script type="application/ld+json">[
      {"@type":"Product","name":"Other","url":"https://shop.test/other"},
      {"@type":"Product","name":"Stol","url":"https://shop.test/chair","offers":{"price":"200","priceCurrency":"DKK"}}]</script></html>''','https://shop.test/chair')
    assert facts['title']=='Stol'
    assert facts['language']=='da'
    assert facts['fields']['offers']['source']=='jsonld[0][1].offers'

def test_ambiguous_collection_is_not_a_product():
    facts=extract_page_facts('<h1>Shop</h1><script type="application/ld+json">[{"@type":"Product","name":"A"},{"@type":"Product","name":"B"}]</script>','https://shop.test')
    assert facts['page_type']=='landing'
    assert not facts['fields']

def test_unsupported_numbers_and_proof_are_removed():
    facts=extract_page_facts('<h1>Build better</h1><p>For small teams</p>','https://site.test')
    result=grounded_copy(ReasoningResult(title='10x faster',proof='50,000 happy customers',variants=[{'title':'Save 80%'}]),facts)
    assert result.title=='Build better'
    assert result.proof is None
    assert result.variants==[]
