# Editorial quality gate

Pixel checks detect broken rendering. Human review determines whether a card is useful.
Create a packet with `python -m backend.scripts.preview_engine.editorial_review packet records.json work/review` using the corpus runner's records. Supply `original_image_url` where captured; otherwise reviewers inspect the original page. Record the generation commit in `revision`.

Review the card at 400px wide against the source page. Rate accuracy, relevance, brand fidelity and small-size readability from 1 (unusable) to 5 (excellent). Accuracy 5 means every factual claim is supported by the page. Record whether editing is required, whether it beats the original preview, reviewer identity, timestamp and notes in `reviews.json`.

Run `python -m backend.scripts.preview_engine.editorial_review score work/review/reviews.json --min-reviews 20 --min-rate .9`. The gate fails on incomplete ratings, duplicate reviews, insufficient reviews or a publishable rate below the threshold. Results are grouped by page type. Include products, articles, profiles, events, landing pages, non-Latin text and held-out customer pages; review at least four examples per primary page type before release. Multiple reviewers are reported as evaluations, not unique cards.

No human ratings or publishability claims are supplied with the implementation. A real review round and customer pilot remain release activities.
