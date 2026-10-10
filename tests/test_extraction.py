from app.services.evidence_pipeline import _classify_record
from app.services.extraction import (
    calculate_effective_count,
    classify_report,
    deduplicate_reports,
    resolve_dimension,
    resolve_product,
)


def test_classify_report_detects_structured_output_issue() -> None:
    report = {
        "title": "Structured output started failing",
        "body": "JSON schema validation now errors on every request. Tool call responses are broken.",
        "source": "github",
    }

    result = classify_report(report)

    assert result["is_change_report"] is True
    assert result["dimension"] == "structured_output"
    assert result["direction"] == "worse"
    assert result["first_hand"] is False
    assert result["contains_reproducible_example"] is True


def test_resolve_product_and_dimension_from_aliases() -> None:
    text = "OpenAI Chat Completions JSON schema validation is regressing"

    assert resolve_product(text) == "openai/chat-completions"
    assert resolve_dimension(text) == "structured_output"


def test_resolve_responses_api_before_generic_openai_aliases() -> None:
    text = "The Responses API schema validation changed without notice and now rejects previously valid schemas."

    assert resolve_product(text) == "openai/responses-api"
    assert resolve_dimension(text) == "structured_output"


def test_weak_openai_mentions_do_not_force_chat_completions() -> None:
    generic_text = "OpenAI has a problem with validation after rollout."
    assert resolve_product(generic_text) == "openai"
    assert resolve_dimension(generic_text) is None

    responses_text = "The Responses API validation changed without notice."
    assert resolve_product(responses_text) == "openai/responses-api"


def test_github_repo_url_does_not_override_ambiguous_issue_text() -> None:
    text = "Structured output responses failing JSON schema validation after rollout. https://github.com/openai/openai-python/issues/4040"
    assert resolve_product(text) == "openai"
    assert resolve_dimension(text) == "structured_output"


def test_probe_metadata_does_not_overrule_weak_evidence_text() -> None:
    result = _classify_record(
        "probe://openai/chat-completions/structured_output",
        {
            "title": "Probe result for openai/chat-completions structured_output",
            "body": "Probe status=degraded success_rate=0.6666666666666666",
            "probe": {
                "status": "degraded",
                "dimension": "structured_output",
                "product": "openai/chat-completions",
            },
        },
        "probe",
    )

    assert result["product"] == "openai/chat-completions"
    assert result["dimension"] == "unknown"
    assert result["classification"]["dimension"] is None


def test_google_gemini_quota_input_is_mapped_to_rate_quota() -> None:
    text = (
        "https://discuss.ai.google.dev/t/this-is-likely-going-to-end-up-in-a-class-action-lawsuit-if-you-dont-stop/99181 "
        "Free tier input tokens for PRO2.5 were reduced to 125,000 tokens with no notice. "
        "IF I HAD A CREDIT CARD ATTACHED this would have caused unfair billing. "
        "NO WAY can I sign up for a paid tier when 20% of the responses are unreliable AND you just change quotas at will. "
        "NOT COOL. "
        "{\"success\":false,\"error\":\"HTTP Error: 429 - {\\n \\\"error\\\": {\\n \\\"code\\\": 429,\\n \\\"message\\\": \\\"You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits.\\\",\\n \\\"status\\\": \\\"RESOURCE_EXHAUSTED\\\",\\n \\\"details\\\": [\\n {\\n \\\"@type\\\": \\\"type.googleapis.com/google.rpc.QuotaFailure\\\",\\n \\\"violations\\\": [\\n {\\n \\\"quotaMetric\\\": \\\"generativelanguage.googleapis.com/generate_content_free_tier_input_token_count\\\",\\n \\\"quotaId\\\": \\\"GenerateContentInputTokensPerModelPerMinute-FreeTier\\\",\\n \\\"quotaDimensions\\\": {\\n \\\"location\\\": \\\"global\\\",\\n \\\"model\\\": \\\"gemini-2.5-pro\\\"\\n },\\n \\\"quotaValue\\\": \\\"125000\\\"\\n }\\n ]\\n },\\n {\\n \\\"@type\\\": \\\"type.googleapis.com/google.rpc.Help\\\",\\n \\\"links\\\": [\\n {\\n \\\"description\\\": \\\"Learn more about Gemini API quotas\\\",\\n \\\"url\\\": \\\"https://ai.google.dev/gemini-api/docs/rate-limits\\\"\\n }\\n ],\\n \\\"@type\\\": \\\"type.googleapis.com/google.rpc.RetryInfo\\\",\\n \\\"retryDelay\\\": \\\"21s\\\"\\n }\\n ]\\n }\\n}\\n\"}"
    )

    assert resolve_product(text) == "google/gemini"
    assert resolve_dimension(text) == "rate_quota"
    assert classify_report({
        "title": "Gemini quota reduction",
        "body": text,
        "url": "https://discuss.ai.google.dev/t/this-is-likely-going-to-end-up-in-a-class-action-lawsuit-if-you-dont-stop/99181",
        "source": "forum",
    })["dimension"] == "rate_quota"


def test_first_hand_detection_uses_word_boundaries() -> None:
    first_hand_report = classify_report({"title": "We are seeing tool call failures", "body": "Our team cannot reproduce structured output anymore."})
    hearsay_report = classify_report({"title": "Heard that JSON schema validation is broken.", "body": "Someone said the rate limits changed."})
    no_pronouns_report = classify_report({"title": "Schema validation broken", "body": "JSON schema validation now errors on every request."})

    assert first_hand_report["first_hand"] is True
    assert hearsay_report["first_hand"] is False
    assert no_pronouns_report["first_hand"] is False

    records = [
        {"id": "a", "title": "tool calling broke", "body": "tool calling broke again", "url": "https://x/1"},
        {"id": "b", "title": "tool calling broke", "body": "tool calling broke again", "url": "https://x/1"},
        {"id": "c", "title": "rate limits changed", "body": "limits are lower", "url": "https://x/2"},
    ]

    deduped, duplicates = deduplicate_reports(records)
    assert len(deduped) == 2
    assert len(duplicates) == 1
    assert calculate_effective_count(raw_count=10, concentration=0.8) < 10
