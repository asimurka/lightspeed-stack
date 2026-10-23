"""Unit tests for Bedrock invokable-id resolution."""

from typing import Any

from providers.inference.bedrock.discovery import (
    first_profile_id_by_foundation_model_id,
    foundation_model_id_from_arn,
    invokable_model_id,
    list_foundation_models,
    list_inference_profiles,
    to_discovered_model,
)
from providers.inference.bedrock.specs import (
    FoundationModelSummary,
    InferenceProfileSummary,
)


def _foundation(
    model_id: str,
    *,
    inference_types: list[str],
    modalities: list[str] | None = None,
) -> FoundationModelSummary:
    """Build a foundation summary for resolution tests."""
    return FoundationModelSummary.model_validate(
        {
            "modelId": model_id,
            "outputModalities": modalities or ["TEXT"],
            "inferenceTypesSupported": inference_types,
        }
    )


def _profile(profile_id: str, *foundation_model_ids: str) -> InferenceProfileSummary:
    """Build a profile summary whose ARNs end with the given model ids."""
    return InferenceProfileSummary.model_validate(
        {
            "inferenceProfileId": profile_id,
            "models": [
                {
                    "modelArn": (
                        f"arn:aws:bedrock:us-east-1::foundation-model/{model_id}"
                    )
                }
                for model_id in foundation_model_ids
            ],
        }
    )


def test_list_foundation_models_parses_summaries(mocker: Any) -> None:
    """Validates ListFoundationModels wire summaries."""
    client = mocker.MagicMock()
    client.list_foundation_models.return_value = {
        "modelSummaries": [
            {
                "modelId": "amazon.titan-embed-text-v2:0",
                "outputModalities": ["EMBEDDING"],
                "inferenceTypesSupported": ["ON_DEMAND"],
            }
        ]
    }

    models = list_foundation_models(client)

    assert len(models) == 1
    assert models[0].model_id == "amazon.titan-embed-text-v2:0"
    client.list_foundation_models.assert_called_once_with()


def test_list_inference_profiles_paginates_system_defined(mocker: Any) -> None:
    """Collects system-defined profiles across paginator pages."""
    client = mocker.MagicMock()
    paginator = mocker.MagicMock()
    paginator.paginate.return_value = [
        {
            "inferenceProfileSummaries": [
                {
                    "inferenceProfileId": "us.openai.gpt-6-astra",
                    "models": [
                        {
                            "modelArn": (
                                "arn:aws:bedrock:us-east-1::foundation-model/"
                                "openai.gpt-6-astra"
                            )
                        }
                    ],
                }
            ]
        },
        {
            "inferenceProfileSummaries": [
                {"inferenceProfileId": "us.amazon.nova-pro-v1:0", "models": []}
            ]
        },
    ]
    client.get_paginator.return_value = paginator

    profiles = list_inference_profiles(client)

    assert [profile.inference_profile_id for profile in profiles] == [
        "us.openai.gpt-6-astra",
        "us.amazon.nova-pro-v1:0",
    ]
    client.get_paginator.assert_called_once_with("list_inference_profiles")
    paginator.paginate.assert_called_once_with(typeEquals="SYSTEM_DEFINED")


def test_to_discovered_model_builds_row_or_skips() -> None:
    """Builds a discovered row when type and wire id are present."""
    model = _foundation(
        "nvidia.nemotron-nano-12b-v2",
        inference_types=["ON_DEMAND"],
    )

    discovered = to_discovered_model(model, {}, "llm")
    assert discovered is not None
    assert discovered.provider_model_id == "nvidia.nemotron-nano-12b-v2"
    assert discovered.model_type == "llm"
    assert to_discovered_model(model, {}, None) is None


def test_foundation_model_id_from_arn_uses_exact_suffix() -> None:
    """Extracts the ARN suffix after foundation-model/."""
    assert (
        foundation_model_id_from_arn(
            "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-pro-v1:0"
        )
        == "amazon.nova-pro-v1:0"
    )
    assert (
        foundation_model_id_from_arn(
            "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-pro-v1:0:300k"
        )
        == "amazon.nova-pro-v1:0:300k"
    )
    assert foundation_model_id_from_arn("arn:aws:bedrock:us-east-1::other/foo") is None
    assert (
        foundation_model_id_from_arn("arn:aws:bedrock:us-east-1::foundation-model/")
        is None
    )


def test_first_profile_id_keeps_first_match_by_exact_suffix() -> None:
    """Indexes the first profile per exact foundation model id suffix."""
    mapping = first_profile_id_by_foundation_model_id(
        [
            _profile("us.amazon.nova-pro-v1:0", "amazon.nova-pro-v1:0"),
            _profile("eu.amazon.nova-pro-v1:0", "amazon.nova-pro-v1:0"),
            _profile(
                "us.amazon.nova-pro-v1:0:300k",
                "amazon.nova-pro-v1:0:300k",
            ),
        ]
    )

    assert mapping == {
        "amazon.nova-pro-v1:0": "us.amazon.nova-pro-v1:0",
        "amazon.nova-pro-v1:0:300k": "us.amazon.nova-pro-v1:0:300k",
    }


def test_invokable_model_id_keeps_on_demand_foundation_id() -> None:
    """Uses the foundation model id when ON_DEMAND is supported."""
    model = _foundation(
        "nvidia.nemotron-nano-12b-v2",
        inference_types=["ON_DEMAND"],
    )

    assert invokable_model_id(model, {}) == "nvidia.nemotron-nano-12b-v2"


def test_invokable_model_id_remaps_profile_only_to_first_profile() -> None:
    """Uses the first matching profile id for profile-only models."""
    model = _foundation(
        "openai.gpt-6-astra",
        inference_types=["INFERENCE_PROFILE"],
    )
    profile_ids = {"openai.gpt-6-astra": "us.openai.gpt-6-astra"}

    assert invokable_model_id(model, profile_ids) == "us.openai.gpt-6-astra"


def test_invokable_model_id_skips_profile_only_without_profile() -> None:
    """Drops profile-only models that have no matching profile."""
    model = _foundation(
        "openai.gpt-6-astra",
        inference_types=["INFERENCE_PROFILE"],
    )

    assert invokable_model_id(model, {}) is None


def test_invokable_model_id_requires_exact_arn_suffix() -> None:
    """Does not treat a shorter foundation id as a match for a longer suffix."""
    model = _foundation(
        "amazon.nova-pro-v1:0:300k",
        inference_types=["INFERENCE_PROFILE"],
    )
    profile_ids = {"amazon.nova-pro-v1:0": "us.amazon.nova-pro-v1:0"}

    assert invokable_model_id(model, profile_ids) is None


def test_invokable_model_id_skips_provisioned_and_empty_types() -> None:
    """Drops provisioned-only models and models with no inference types."""
    provisioned = _foundation(
        "amazon.nova-pro-v1:0:300k",
        inference_types=["PROVISIONED"],
    )
    empty = _foundation(
        "amazon.titan-embed-text-v2:0:8k",
        inference_types=[],
        modalities=["EMBEDDING"],
    )

    assert invokable_model_id(provisioned, {}) is None
    assert invokable_model_id(empty, {}) is None
