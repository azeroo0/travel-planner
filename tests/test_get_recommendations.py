import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import SQLAlchemyError

from backend.clients import ollama_client
from backend.db.session import get_session
from backend.main import app
from backend.repositories import recommendations as repository
from backend.schemas.recommendations import FitResult, PlaceRecommendationQuery, RecommendedPlace
from backend.services import recommendations as service


class FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return self.rows


class OllamaClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_format_is_only_sent_when_requested(self):
        payloads = []

        def respond(request):
            payloads.append(json.loads(request.content))
            return httpx.Response(200, json={"message": {"content": "{}"}})

        original_client = httpx.AsyncClient

        def test_client(*args, **kwargs):
            return original_client(*args, transport=httpx.MockTransport(respond), **kwargs)

        settings = SimpleNamespace(ollama_base_url="http://test", ollama_timeout_seconds=5)
        with (
            patch.object(ollama_client, "get_settings", return_value=settings),
            patch.object(ollama_client.httpx, "AsyncClient", side_effect=test_client),
        ):
            await ollama_client.OllamaClient().chat("test-model", [])
            await ollama_client.OllamaClient().chat("test-model", [], format={"type": "object"})
        self.assertNotIn("format", payloads[0])
        self.assertEqual(payloads[1]["format"], {"type": "object"})


class RepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_category_uses_category_table_and_region_relation(self):
        session = FakeSession([(31, "해동용궁사", "attraction", "haeundae")])
        candidates = await repository.recommendation_candidates(
            session, category="attraction", after_id=0, batch_size=12,
        )
        sql = str(session.statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
        self.assertEqual(candidates[0].place_id, 31)
        self.assertIn("JOIN place_categories", sql)
        self.assertIn("JOIN districts", sql)
        self.assertIn("JOIN regions", sql)
        self.assertIn("category_code = 'attraction'", sql)
        self.assertIn("LIMIT 12", sql)

    async def test_reviews_are_partitioned_by_place_and_exclude_synthetic(self):
        session = FakeSession([(31, 101, "바다가 보여요"), (32, 201, "조용해요")])
        reviews = await repository.candidate_reviews(session, [31, 32], per_place=3)
        sql = str(session.statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
        self.assertEqual(reviews, {31: {101: "바다가 보여요"}, 32: {201: "조용해요"}})
        self.assertIn("PARTITION BY reviews.place_id", sql)
        self.assertIn("reviews.is_synthetic IS false", sql)
        self.assertIn("review_rank <= 3", sql)
        self.assertIn("reviews.review_id", sql)


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.place_a = repository.PlaceCandidate(31, "뮤지엄 원", "attraction", "haeundae")
        self.place_b = repository.PlaceCandidate(32, "요트클럽", "attraction", "haeundae")
        self.text_a = "미술관의 전시가 좋았습니다. " + "관람하기 편했습니다. " * 50
        self.text_b = "사진에 보듯 데크가 수십군데 뚫려있어 아주 위험합니다."

    def model_output(self, *items):
        return json.dumps({"recommendations": list(items)}, ensure_ascii=False)

    async def test_verified_review_id_and_full_evidence_only_reach_second_call(self):
        first = self.model_output({"place_id": 31, "fit": 78, "review_ids": [101]})
        client = SimpleNamespace(chat=AsyncMock(side_effect=[first, '{"reason":"전시가 좋다는 리뷰가 있어요."}']))
        with (
            patch.object(repository, "recommendation_candidates", new=AsyncMock(side_effect=[[self.place_a, self.place_b], []])) as candidates,
            patch.object(repository, "candidate_reviews", new=AsyncMock(return_value={
                31: {101: self.text_a, 102: "다른 미술관 리뷰"}, 32: {201: self.text_b},
            })),
            patch.object(service, "get_settings", return_value=SimpleNamespace(ollama_model="test-model")),
        ):
            results = await service.recommend_places(
                object(), PlaceRecommendationQuery(category="attraction", limit=1), client,
            )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].place.place_id, 31)
        self.assertEqual(results[0].reason, "전시가 좋다는 리뷰가 있어요.")
        self.assertEqual(results[0].strengths, [])
        self.assertEqual(results[0].cautions, [])
        self.assertEqual(candidates.await_args_list[0].kwargs["category"], "attraction")
        calls = client.chat.await_args_list
        self.assertEqual(len(calls), 2)
        first_payload = json.loads(calls[0].args[1][1]["content"])
        self.assertEqual([place["place_id"] for place in first_payload["places"]], [31, 32])
        self.assertEqual(first_payload["places"][0]["reviews"][0],
                         {"review_id": 101, "text": self.text_a[:400]})
        self.assertNotIn(self.text_a, calls[0].args[1][1]["content"])
        self.assertIn("recommendations", calls[0].kwargs["format"]["properties"])
        second_payload = json.loads(calls[1].args[1][1]["content"])
        self.assertEqual(second_payload["place"]["place_id"], 31)
        self.assertEqual(second_payload["reviews"], [{"review_id": 101, "review_text": self.text_a}])
        self.assertNotIn(self.text_b, calls[1].args[1][1]["content"])
        self.assertNotIn("places", second_payload)
        self.assertIn("reason", calls[1].kwargs["format"]["properties"])
        selected = service._parse_place_recommendations(first, {31: self.place_a},
                                                         {31: {101: self.text_a}}, 1)
        self.assertEqual(selected[0].reviews[101], self.text_a)

    async def test_other_places_review_id_is_rejected(self):
        output = self.model_output({"place_id": 31, "fit": 78, "review_ids": [201]})
        with self.assertRaises(service.PlaceModelOutputInvalid):
            service._parse_place_recommendations(output, {31: self.place_a, 32: self.place_b},
                                                  {31: {101: self.text_a}, 32: {201: self.text_b}}, 10)

    async def test_unknown_review_id_and_place_id_are_rejected(self):
        for item in (
            {"place_id": 31, "fit": 78, "review_ids": [999999999]},
            {"place_id": 999, "fit": 78, "review_ids": [101]},
        ):
            with self.subTest(item=item), self.assertRaises(service.PlaceModelOutputInvalid):
                service._parse_place_recommendations(self.model_output(item), {31: self.place_a},
                                                      {31: {101: self.text_a}}, 10)

    async def test_invalid_selection_does_not_block_other_valid_selection(self):
        output = self.model_output(
            {"place_id": 31, "fit": 80, "review_ids": [201]},
            {"place_id": 32, "fit": 70, "review_ids": [201]},
        )
        selections = service._parse_place_recommendations(
            output, {31: self.place_a, 32: self.place_b},
            {31: {101: self.text_a}, 32: {201: self.text_b}}, 10,
        )
        self.assertEqual([item.place.place_id for item in selections], [32])

    async def test_batch_limit_uses_highest_fit_not_model_order(self):
        output = self.model_output(
            {"place_id": 31, "fit": 40, "review_ids": [101]},
            {"place_id": 32, "fit": 90, "review_ids": [201]},
        )
        selections = service._parse_place_recommendations(
            output, {31: self.place_a, 32: self.place_b},
            {31: {101: self.text_a}, 32: {201: self.text_b}}, 1,
        )
        self.assertEqual([item.place.place_id for item in selections], [32])

    async def test_no_reviews_returns_empty_without_model(self):
        client = SimpleNamespace(chat=AsyncMock())
        with (
            patch.object(repository, "recommendation_candidates", new=AsyncMock(side_effect=[[self.place_a], []])),
            patch.object(repository, "candidate_reviews", new=AsyncMock(return_value={})),
            patch.object(service, "get_settings", return_value=SimpleNamespace(ollama_model=None)),
        ):
            self.assertEqual(await service.recommend_places(object(), PlaceRecommendationQuery(), client), [])
        client.chat.assert_not_awaited()

    async def test_invalid_first_model_output_and_fit(self):
        for output in (
            "not json",
            self.model_output({"place_id": 31, "fit": 101, "review_ids": [101]}),
            self.model_output({"place_id": 31, "fit": "bad", "review_ids": [101]}),
            self.model_output({"place_id": 31, "fit": "80", "review_ids": [101]}),
        ):
            with self.subTest(output=output):
                with self.assertRaises(service.PlaceModelOutputInvalid):
                    service._parse_place_recommendations(output, {31: self.place_a},
                                                          {31: {101: self.text_a}}, 10)

    async def test_model_connection_failure(self):
        client = SimpleNamespace(chat=AsyncMock(side_effect=httpx.ConnectError("offline")))
        with (
            patch.object(repository, "recommendation_candidates", new=AsyncMock(side_effect=[[self.place_a], []])),
            patch.object(repository, "candidate_reviews", new=AsyncMock(return_value={31: {101: self.text_a}})),
            patch.object(service, "get_settings", return_value=SimpleNamespace(ollama_model="test-model")),
        ):
            with self.assertRaises(service.PlaceModelUnavailable):
                await service.recommend_places(object(), PlaceRecommendationQuery(), client)

    async def test_global_limit_across_batches(self):
        client = SimpleNamespace(chat=AsyncMock(side_effect=[
            self.model_output({"place_id": 31, "fit": 60, "review_ids": [101]}),
            self.model_output({"place_id": 32, "fit": 90, "review_ids": [201]}),
            '{"reason":"요트클럽 리뷰를 근거로 합니다."}',
        ]))
        with (
            patch.object(repository, "recommendation_candidates", new=AsyncMock(side_effect=[[self.place_a], [self.place_b], []])),
            patch.object(repository, "candidate_reviews", new=AsyncMock(side_effect=[
                {31: {101: self.text_a}}, {32: {201: self.text_b}},
            ])),
            patch.object(service, "get_settings", return_value=SimpleNamespace(ollama_model="test-model")),
        ):
            results = await service.recommend_places(object(), PlaceRecommendationQuery(limit=1), client)
        self.assertEqual([item.place.place_id for item in results], [32])
        self.assertEqual(client.chat.await_count, 3)
        second_payload = json.loads(client.chat.await_args_list[2].args[1][1]["content"])
        self.assertEqual(second_payload["place"]["place_id"], 32)

    async def test_failed_second_reason_skips_one_and_keeps_other(self):
        first = self.model_output(
            {"place_id": 31, "fit": 90, "review_ids": [101]},
            {"place_id": 32, "fit": 80, "review_ids": [201]},
        )
        client = SimpleNamespace(chat=AsyncMock(side_effect=[first, "not json", '{"reason":"방문 후기입니다."}']))
        with (
            patch.object(repository, "recommendation_candidates", new=AsyncMock(side_effect=[[self.place_a, self.place_b], []])),
            patch.object(repository, "candidate_reviews", new=AsyncMock(return_value={
                31: {101: self.text_a}, 32: {201: self.text_b},
            })),
            patch.object(service, "get_settings", return_value=SimpleNamespace(ollama_model="test-model")),
        ):
            results = await service.recommend_places(object(), PlaceRecommendationQuery(limit=2), client)
        self.assertEqual([item.place.place_id for item in results], [32])

    async def test_second_model_http_error_skips_failed_recommendation(self):
        first = self.model_output(
            {"place_id": 31, "fit": 90, "review_ids": [101]},
            {"place_id": 32, "fit": 80, "review_ids": [201]},
        )
        client = SimpleNamespace(chat=AsyncMock(side_effect=[
            first, httpx.ConnectError("offline"), '{"reason":"요트클럽 리뷰를 근거로 합니다."}',
        ]))
        with (
            patch.object(repository, "recommendation_candidates", new=AsyncMock(side_effect=[[self.place_a, self.place_b], []])),
            patch.object(repository, "candidate_reviews", new=AsyncMock(return_value={
                31: {101: self.text_a}, 32: {201: self.text_b},
            })),
            patch.object(service, "get_settings", return_value=SimpleNamespace(ollama_model="test-model")),
        ):
            results = await service.recommend_places(object(), PlaceRecommendationQuery(limit=2), client)
        self.assertEqual([item.place.place_id for item in results], [32])

    async def test_all_second_reasons_fail_returns_502_error(self):
        first = self.model_output({"place_id": 31, "fit": 90, "review_ids": [101]})
        client = SimpleNamespace(chat=AsyncMock(side_effect=[first, '{"reason":"   "}']))
        with (
            patch.object(repository, "recommendation_candidates", new=AsyncMock(side_effect=[[self.place_a], []])),
            patch.object(repository, "candidate_reviews", new=AsyncMock(return_value={31: {101: self.text_a}})),
            patch.object(service, "get_settings", return_value=SimpleNamespace(ollama_model="test-model")),
        ):
            with self.assertRaises(service.PlaceModelOutputInvalid):
                await service.recommend_places(object(), PlaceRecommendationQuery(limit=1), client)


class RouteTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        async def fake_session():
            yield object()
        app.dependency_overrides[get_session] = fake_session
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        app.dependency_overrides.clear()

    async def test_anonymous_get_and_existing_post_auth(self):
        with patch.object(service, "recommend_places", new=AsyncMock(return_value=[])) as recommend:
            get = await self.client.get("/api/v1/recommendations", params={"with": "parents", "pri": "sea,quiet", "limit": 2})
            post = await self.client.post("/api/v1/recommendations", json={"scrap_ids": [1], "requirements": "바다"})
        self.assertEqual(get.status_code, 200)
        self.assertEqual(get.json(), [])
        self.assertEqual(post.status_code, 401)
        query = recommend.await_args.args[1]
        self.assertEqual(query.companion, "parents")
        self.assertEqual(query.priorities, ["sea", "quiet"])
        self.assertEqual(query.limit, 2)

    async def test_invalid_conditions(self):
        for params in ({"category": "invalid"}, {"pri": "sea,unknown"}, {"limit": 51}, {"walk": "invalid"}):
            with self.subTest(params=params):
                response = await self.client.get("/api/v1/recommendations", params=params)
                self.assertEqual(response.status_code, 422)

    async def test_fit_result_matches_frontend_shape(self):
        result = FitResult(
            place=RecommendedPlace(place_id=31, name="해동용궁사", category="attraction", region="haeundae"),
            fit=78, reason="바다가 보인다는 리뷰가 있어요.", strengths=[], cautions=[],
        )
        with patch.object(service, "recommend_places", new=AsyncMock(return_value=[result])):
            response = await self.client.get("/api/v1/recommendations")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{
            "place": {"place_id": 31, "name": "해동용궁사", "category": "attraction", "region": "haeundae"},
            "fit": 78.0, "reason": "바다가 보인다는 리뷰가 있어요.", "strengths": [], "cautions": [],
        }])

    async def test_database_and_model_errors_are_http_errors(self):
        for error, status in (
            (SQLAlchemyError("offline"), 503),
            (service.PlaceModelUnavailable("offline"), 503),
            (service.PlaceModelOutputInvalid("invalid"), 502),
        ):
            with self.subTest(error=error):
                with patch.object(service, "recommend_places", new=AsyncMock(side_effect=error)):
                    response = await self.client.get("/api/v1/recommendations")
                self.assertEqual(response.status_code, status)
