from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase
from pydantic_ai import models

from core import llm


class SemanticSearchToolTests(SimpleTestCase):
    async def test_searches_with_the_query_the_model_wrote(self):
        index = mock.MagicMock()
        index.search.return_value = {
            "result": {
                "hits": [
                    {
                        "_id": "i-130-1",
                        "_score": 0.87,
                        "fields": {
                            "category": "green-card",
                            "chunk_text": "Use Form I-130 to petition for a relative.",
                        },
                    }
                ]
            }
        }
        pinecone = mock.MagicMock()
        pinecone.Index.return_value = index
        ctx = SimpleNamespace(deps=llm.Deps(pinecone=pinecone, namespace="us"))
        query = "Form I-130 petition for the spouse of a US citizen"

        # Model requests are blocked: the tool must search on the query it was
        # given rather than asking an LLM to rewrite it.
        with mock.patch.object(models, "ALLOW_MODEL_REQUESTS", False):
            result = await llm.semantic_search(ctx, query)

        # Searches the injected client, on the query it was handed, in the
        # namespace from Deps (not a hardcoded one).
        self.assertEqual(index.search.call_args.kwargs["query"]["inputs"]["text"], query)
        self.assertEqual(index.search.call_args.kwargs["namespace"], "us")
        self.assertEqual(result["namespace"], "us")
        self.assertEqual(result["query"], query)
        self.assertEqual(result["matches"][0]["id"], "i-130-1")
