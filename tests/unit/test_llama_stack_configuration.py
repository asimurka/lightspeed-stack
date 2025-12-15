"""Unit tests for functions defined in src/llama_stack_configuration.py."""

from pathlib import Path

from typing import Any

import pytest
import yaml

from pydantic import SecretStr

from models.config import (
    ByokRag,
    Configuration,
    ServiceConfiguration,
    LlamaStackConfiguration,
    UserDataCollection,
)

from constants import (
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_DIMENSION,
)

from llama_stack_configuration import (
    generate_configuration,
    construct_vector_dbs_section,
    construct_vector_io_providers_section,
)


def byok_to_dict(byok: ByokRag) -> dict[str, Any]:
    """Convert ByokRag to dict for testing."""
    return {
        "vector_db_id": byok.vector_db_id,
        "embedding_model": byok.embedding_model,
        "embedding_dimension": byok.embedding_dimension,
        "rag_type": byok.rag_type,
    }


def test_construct_vector_dbs_section_init() -> None:
    """Test the function construct_vector_dbs_section for no vector_dbs configured before."""
    ls_config: dict[str, Any] = {}
    byok_rag: list[dict[str, Any]] = []
    output = construct_vector_dbs_section(ls_config, byok_rag)
    assert len(output) == 0


def test_construct_vector_dbs_section_init_with_existing_data() -> None:
    """Test the function construct_vector_dbs_section for vector_dbs configured before."""
    ls_config = {
        "vector_dbs": [
            {
                "vector_db_id": "vector_db_id_1",
                "provider_id": "provier_id_1",
                "embedding_model": "embedding_model_1",
                "embedding_dimension": 1,
            },
            {
                "vector_db_id": "vector_db_id_2",
                "provider_id": "provier_id_2",
                "embedding_model": "embedding_model_2",
                "embedding_dimension": 2,
            },
        ]
    }
    byok_rag: list[dict[str, Any]] = []
    output = construct_vector_dbs_section(ls_config, byok_rag)
    assert len(output) == 2
    assert output[0] == {
        "vector_db_id": "vector_db_id_1",
        "provider_id": "provier_id_1",
        "embedding_model": "embedding_model_1",
        "embedding_dimension": 1,
    }
    assert output[1] == {
        "vector_db_id": "vector_db_id_2",
        "provider_id": "provier_id_2",
        "embedding_model": "embedding_model_2",
        "embedding_dimension": 2,
    }


def test_construct_vector_dbs_section_append() -> None:
    """Test the function construct_vector_dbs_section for no vector_dbs configured before."""
    ls_config: dict[str, Any] = {}
    byok_rag = [
        byok_to_dict(ByokRag(
            rag_id="rag_id_1",
            vector_db_id="vector_db_id_1",
            db_path=Path("tests/configuration/rag.txt"),
        )),
        byok_to_dict(ByokRag(
            rag_id="rag_id_2",
            vector_db_id="vector_db_id_2",
            db_path=Path("tests/configuration/rag.txt"),
        )),
    ]
    output = construct_vector_dbs_section(ls_config, byok_rag)
    assert len(output) == 2
    assert output[0] == {
        "vector_db_id": "vector_db_id_1",
        "provider_id": "byok_vector_db_id_1",
        "embedding_model": DEFAULT_EMBEDDING_MODEL,
        "embedding_dimension": DEFAULT_EMBEDDING_DIMENSION,
    }
    assert output[1] == {
        "vector_db_id": "vector_db_id_2",
        "provider_id": "byok_vector_db_id_2",
        "embedding_model": DEFAULT_EMBEDDING_MODEL,
        "embedding_dimension": DEFAULT_EMBEDDING_DIMENSION,
    }


def test_construct_vector_dbs_section_full_merge() -> None:
    """Test the function construct_vector_dbs_section for vector_dbs configured before."""
    ls_config = {
        "vector_dbs": [
            {
                "vector_db_id": "vector_db_id_1",
                "provider_id": "provier_id_1",
                "embedding_model": "embedding_model_1",
                "embedding_dimension": 1,
            },
            {
                "vector_db_id": "vector_db_id_2",
                "provider_id": "provier_id_2",
                "embedding_model": "embedding_model_2",
                "embedding_dimension": 2,
            },
        ]
    }
    byok_rag = [
        byok_to_dict(ByokRag(
            rag_id="rag_id_1",
            vector_db_id="vector_db_id_1",
            db_path=Path("tests/configuration/rag.txt"),
        )),
        byok_to_dict(ByokRag(
            rag_id="rag_id_2",
            vector_db_id="vector_db_id_2",
            db_path=Path("tests/configuration/rag.txt"),
        )),
    ]
    output = construct_vector_dbs_section(ls_config, byok_rag)
    assert len(output) == 4
    assert output[0] == {
        "vector_db_id": "vector_db_id_1",
        "provider_id": "provier_id_1",
        "embedding_model": "embedding_model_1",
        "embedding_dimension": 1,
    }
    assert output[1] == {
        "vector_db_id": "vector_db_id_2",
        "provider_id": "provier_id_2",
        "embedding_model": "embedding_model_2",
        "embedding_dimension": 2,
    }
    assert output[2] == {
        "vector_db_id": "vector_db_id_1",
        "provider_id": "byok_vector_db_id_1",
        "embedding_model": DEFAULT_EMBEDDING_MODEL,
        "embedding_dimension": DEFAULT_EMBEDDING_DIMENSION,
    }
    assert output[3] == {
        "vector_db_id": "vector_db_id_2",
        "provider_id": "byok_vector_db_id_2",
        "embedding_model": DEFAULT_EMBEDDING_MODEL,
        "embedding_dimension": DEFAULT_EMBEDDING_DIMENSION,
    }


def test_construct_vector_io_providers_section_init() -> None:
    """Test construct_vector_io_providers_section for no vector_io_providers configured before."""
    ls_config: dict[str, Any] = {"providers": {}}
    byok_rag: list[dict[str, Any]] = []
    output = construct_vector_io_providers_section(ls_config, byok_rag)
    assert len(output) == 0


def test_construct_vector_io_providers_section_init_with_existing_data() -> None:
    """Test construct_vector_io_providers_section for vector_io_providers configured before."""
    ls_config = {
        "providers": {
            "vector_io": [
                {
                    "provider_id": "faiss_1",
                    "provider_type": "inline::faiss",
                },
                {
                    "provider_id": "faiss_2",
                    "provider_type": "inline::faiss",
                },
            ]
        }
    }
    byok_rag: list[dict[str, Any]] = []
    output = construct_vector_io_providers_section(ls_config, byok_rag)
    assert len(output) == 2
    assert output[0] == {
        "provider_id": "faiss_1",
        "provider_type": "inline::faiss",
    }
    assert output[1] == {
        "provider_id": "faiss_2",
        "provider_type": "inline::faiss",
    }


def test_construct_vector_io_providers_section_append() -> None:
    """Test construct_vector_io_providers_section for no vector_io_providers configured before."""
    ls_config: dict[str, Any] = {"providers": {}}
    byok_rag = [
        byok_to_dict(ByokRag(
            rag_id="rag_id_1",
            vector_db_id="vector_db_id_1",
            db_path=Path("tests/configuration/rag.txt"),
        )),
        byok_to_dict(ByokRag(
            rag_id="rag_id_2",
            vector_db_id="vector_db_id_2",
            db_path=Path("tests/configuration/rag.txt"),
        )),
    ]
    output = construct_vector_io_providers_section(ls_config, byok_rag)
    assert len(output) == 2
    assert output[0] == {
        "provider_id": "byok_vector_db_id_1",
        "provider_type": "inline::faiss",
        "config": {
            "kvstore": {
                "db_path": ".llama/vector_db_id_1.db",
                "namespace": None,
                "type": "sqlite",
            },
        },
    }
    assert output[1] == {
        "provider_id": "byok_vector_db_id_2",
        "provider_type": "inline::faiss",
        "config": {
            "kvstore": {
                "db_path": ".llama/vector_db_id_2.db",
                "namespace": None,
                "type": "sqlite",
            },
        },
    }


def test_construct_vector_io_providers_section_full_merge() -> None:
    """Test construct_vector_io_providers_section for vector_io_providers configured before."""
    ls_config = {
        "providers": {
            "vector_io": [
                {
                    "provider_id": "faiss_1",
                    "provider_type": "inline::faiss",
                },
                {
                    "provider_id": "faiss_2",
                    "provider_type": "inline::faiss",
                },
            ]
        }
    }
    byok_rag = [
        byok_to_dict(ByokRag(
            rag_id="rag_id_1",
            vector_db_id="vector_db_id_1",
            db_path=Path("tests/configuration/rag.txt"),
        )),
        byok_to_dict(ByokRag(
            rag_id="rag_id_2",
            vector_db_id="vector_db_id_2",
            db_path=Path("tests/configuration/rag.txt"),
        )),
    ]
    output = construct_vector_io_providers_section(ls_config, byok_rag)
    assert len(output) == 4
    assert output[0] == {
        "provider_id": "faiss_1",
        "provider_type": "inline::faiss",
    }
    assert output[1] == {
        "provider_id": "faiss_2",
        "provider_type": "inline::faiss",
    }
    assert output[2] == {
        "provider_id": "byok_vector_db_id_1",
        "provider_type": "inline::faiss",
        "config": {
            "kvstore": {
                "db_path": ".llama/vector_db_id_1.db",
                "namespace": None,
                "type": "sqlite",
            },
        },
    }
    assert output[3] == {
        "provider_id": "byok_vector_db_id_2",
        "provider_type": "inline::faiss",
        "config": {
            "kvstore": {
                "db_path": ".llama/vector_db_id_2.db",
                "namespace": None,
                "type": "sqlite",
            },
        },
    }


def test_generate_configuration_no_input_file(tmpdir: Path) -> None:
    """Test the function to generate configuration when input file does not exist."""
    cfg = Configuration(
        name="test_name",
        service=ServiceConfiguration(),
        llama_stack=LlamaStackConfiguration(
            use_as_library_client=True,
            library_client_config_path="tests/configuration/run.yaml",
            api_key=SecretStr("whatever"),
        ),
        user_data_collection=UserDataCollection(
            feedback_enabled=False, feedback_storage=None
        ),
    )
    outfile = tmpdir / "run.xml"
    # try to generate new configuration file
    with pytest.raises(FileNotFoundError, match="No such file"):
        generate_configuration("/does/not/exist", str(outfile), cfg.model_dump())


def test_generate_configuration_proper_input_file_no_byok(tmpdir: Path) -> None:
    """Test the function to generate configuration when input file exists."""
    cfg = Configuration(
        name="test_name",
        service=ServiceConfiguration(),
        llama_stack=LlamaStackConfiguration(
            use_as_library_client=True,
            library_client_config_path="tests/configuration/run.yaml",
            api_key=SecretStr("whatever"),
        ),
        user_data_collection=UserDataCollection(
            feedback_enabled=False, feedback_storage=None
        ),
    )
    outfile = tmpdir / "run.xml"
    # try to generate new configuration file
    generate_configuration("tests/configuration/run.yaml", str(outfile), cfg.model_dump())

    with open(outfile, "r", encoding="utf-8") as fin:
        generated = yaml.safe_load(fin)
        assert "vector_dbs" in generated
        assert "providers" in generated
        assert "vector_io" in generated["providers"]


def test_generate_configuration_proper_input_file_configured_byok(tmpdir: Path) -> None:
    """Test the function to generate configuration when BYOK RAG should be added."""
    cfg = Configuration(
        name="test_name",
        service=ServiceConfiguration(),
        llama_stack=LlamaStackConfiguration(
            use_as_library_client=True,
            library_client_config_path="tests/configuration/run.yaml",
            api_key=SecretStr("whatever"),
        ),
        user_data_collection=UserDataCollection(
            feedback_enabled=False, feedback_storage=None
        ),
        byok_rag=[
            ByokRag(
                rag_id="rag_id_1",
                vector_db_id="vector_db_id_1",
                db_path=Path("tests/configuration/rag.txt"),
            ),
            ByokRag(
                rag_id="rag_id_2",
                vector_db_id="vector_db_id_2",
                db_path=Path("tests/configuration/rag.txt"),
            ),
        ],
    )
    outfile = tmpdir / "run.xml"
    # try to generate new configuration file
    generate_configuration("tests/configuration/run.yaml", str(outfile), cfg.model_dump())

    with open(outfile, "r", encoding="utf-8") as fin:
        generated = yaml.safe_load(fin)
        assert "vector_dbs" in generated
        assert "providers" in generated
        assert "vector_io" in generated["providers"]
