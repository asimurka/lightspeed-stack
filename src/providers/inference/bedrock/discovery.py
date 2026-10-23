"""Resolve invokable Bedrock wire ids from foundation and profile summaries."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Optional

from botocore.client import BaseClient

from providers.inference.bedrock.specs import (
    FoundationModelSummary,
    InferenceProfileSummary,
)
from providers.inference.catalog import DiscoveredModel
from providers.inference.types import ModelType

FOUNDATION_MODEL_ARN_MARKER = "foundation-model/"
ON_DEMAND_INFERENCE_TYPE = "ON_DEMAND"
INFERENCE_PROFILE_INFERENCE_TYPE = "INFERENCE_PROFILE"


def list_foundation_models(client: BaseClient) -> list[FoundationModelSummary]:
    """Parse ListFoundationModels summaries from the control-plane client.

    Args:
        client: Bedrock control-plane client.

    Returns:
        Foundation model summaries used for discovery.

    """
    response = client.list_foundation_models()
    return [
        FoundationModelSummary.model_validate(summary)
        for summary in response.get("modelSummaries", [])
    ]


def list_inference_profiles(client: BaseClient) -> list[InferenceProfileSummary]:
    """Parse paginated system-defined inference profiles.

    Args:
        client: Bedrock control-plane client.

    Returns:
        Inference profile summaries in API order.

    """
    paginator = client.get_paginator("list_inference_profiles")
    pages = paginator.paginate(typeEquals="SYSTEM_DEFINED")
    return [
        InferenceProfileSummary.model_validate(summary)
        for page in pages
        for summary in page.get("inferenceProfileSummaries", [])
    ]


def foundation_model_id_from_arn(model_arn: str) -> Optional[str]:
    """Return the foundation model id after the ARN marker.

    Args:
        model_arn: Bedrock model ARN, typically
            ``arn:aws:bedrock:<region>::foundation-model/<modelId>``.

    Returns:
        The exact suffix after ``foundation-model/``, or None when the
        marker is missing or the suffix is empty.

    """
    _, marker, suffix = model_arn.partition(FOUNDATION_MODEL_ARN_MARKER)
    if not marker or not suffix:
        return None
    return suffix


def first_profile_id_by_foundation_model_id(
    profiles: Iterable[InferenceProfileSummary],
) -> dict[str, str]:
    """Map each foundation model id to the first matching profile id.

    Later profiles for the same foundation model id are ignored.

    Args:
        profiles: Inference profile summaries in API order.

    Returns:
        Foundation model id to the first inference profile id that
        referenced it.

    """
    mapping: dict[str, str] = {}
    for profile in profiles:
        for model in profile.models:
            foundation_model_id = foundation_model_id_from_arn(model.model_arn)
            if foundation_model_id is None or foundation_model_id in mapping:
                continue
            mapping[foundation_model_id] = profile.inference_profile_id
    return mapping


def invokable_model_id(
    model: FoundationModelSummary,
    profile_ids_by_foundation_id: Mapping[str, str],
) -> Optional[str]:
    """Return a wire id PAI can call, or None to drop the model.

    Drops models with no inference types, provisioned-only models, and
    profile-only models that have no matching inference profile.

    Args:
        model: Foundation model summary from ListFoundationModels.
        profile_ids_by_foundation_id: First-profile map keyed by foundation
            model id.

    Returns:
        The foundation ``modelId`` when on-demand inference is supported,
        otherwise the first matching inference profile id, or None.

    """
    inference_types = model.inference_types_supported
    if not inference_types:
        return None
    if ON_DEMAND_INFERENCE_TYPE in inference_types:
        return model.model_id
    if INFERENCE_PROFILE_INFERENCE_TYPE not in inference_types:
        return None
    return profile_ids_by_foundation_id.get(model.model_id)


def to_discovered_model(
    model: FoundationModelSummary,
    profile_ids_by_foundation_id: Mapping[str, str],
    model_type: Optional[ModelType],
) -> Optional[DiscoveredModel]:
    """Build a catalog discovery row when the model is invokable.

    Args:
        model: Foundation model summary from ListFoundationModels.
        profile_ids_by_foundation_id: First matching profile id per
            foundation model id.
        model_type: Inferred catalog type, or None to drop the model.

    Returns:
        A discovered model with an invokable wire id, or None when the
        type is missing or no invokable id exists.

    """
    if model_type is None:
        return None
    provider_model_id = invokable_model_id(model, profile_ids_by_foundation_id)
    if provider_model_id is None:
        return None
    return DiscoveredModel(
        provider_model_id=provider_model_id,
        model_type=model_type,
    )
