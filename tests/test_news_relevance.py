import os
import unittest
from collections import Counter


# Минимальные env для безопасного импорта news_monitor в тестах
os.environ.setdefault("SUPABASE_URL", "https://example.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-key")
os.environ.setdefault("GROQ_API_KEY", "test-key")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-key")
os.environ.setdefault("TELEGRAM_CHAT_ID", "1")

import news_monitor  # noqa: E402


class NewsRelevanceTests(unittest.TestCase):
    def test_taxi_gets_strong_penalty(self):
        base = {
            "title": "Компания внедрила FMS-платформу для автопарка",
            "summary": "Запуск с телематикой и контролем топлива",
            "content_text": "Мониторинг транспорта, тахографы, рост эффективности на 18%",
            "post_date": "2026-04-01T10:00:00",
            "source_type": "telegram",
            "channel_id": 1,
        }
        taxi = dict(base)
        taxi["content_text"] += " Также обсуждают рынок такси."

        base_score = news_monitor.score_for_digest_top(base)
        taxi_score = news_monitor.score_for_digest_top(taxi)

        self.assertIn("taxi", taxi_score["penalty_flags"])
        self.assertLess(taxi_score["score"], base_score["score"])

    def test_non_road_transport_penalty(self):
        post = {
            "title": "Железнодорожный и морской транспорт нарастили объёмы",
            "summary": "Новости портов и судоходства",
            "content_text": "Без связи с автоперевозками и FMS",
            "post_date": "2026-04-01T10:00:00",
            "source_type": "website",
            "post_url": "https://example.com/news/1",
        }
        score = news_monitor.score_for_digest_top(post)
        self.assertIn("non_road_transport", score["penalty_flags"])
        self.assertLessEqual(score["score"], 40)

    def test_select_top_posts_bounds_and_source_cap(self):
        candidates = []
        scores = [95, 92, 90, 88, 86, 84, 82, 80, 78, 76]
        sources = [1, 1, 1, 2, 2, 2, 3, 3, 4, 5]
        for idx, (score, source_id) in enumerate(zip(scores, sources), start=1):
            candidates.append({
                "id": idx,
                "title": f"Post {idx}",
                "summary": "summary",
                "content_text": "content",
                "post_date": f"2026-04-{idx:02d}T10:00:00",
                "source_type": "telegram",
                "channel_id": source_id,
                "digest_score": score,
                "digest_reasons": ["test"],
                "digest_penalty_flags": [],
            })

        top = news_monitor.select_top_posts(candidates, min_score=70)
        self.assertGreaterEqual(len(top), 5)
        self.assertLessEqual(len(top), 7)

        source_keys = [f"{p.get('source_type')}:{p.get('channel_id')}" for p in top]
        counts = Counter(source_keys)
        self.assertTrue(all(v <= 2 for v in counts.values()))


if __name__ == "__main__":
    unittest.main()
