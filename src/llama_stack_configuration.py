"""Llama Stack configuration handling."""

from typing import Any

import yaml

from log import get_logger
from models.config import ByokRag, Configuration

logger = get_logger(__name__)


# pylint: disable=too-many-ancestors
class YamlDumper(yaml.Dumper):
    """Custom YAML dumper with proper indentation levels."""

    def increase_indent(self, flow: bool = False, indentless: bool = False) -> None:
        """Control the indentation level of formatted YAML output."""
        _ = indentless
        return super().increase_indent(flow, False)


def generate_configuration(
    input_file: str, output_file: str, config: Configuration
) -> None:
    """Generate new Llama Stack configuration."""
    logger.info("Reading Llama Stack configuration from file %s", input_file)

    with open(input_file, "r", encoding="utf-8") as file:
        ls_config = yaml.safe_load(file)

    if len(config.byok_rag) == 0:
        logger.info("BYOK RAG is not configured: finishing")
    else:
        logger.info("Processing Llama Stack configuration")
        # create or update configuration section vector_dbs
        ls_config["vector_dbs"] = construct_vector_dbs_section(
            ls_config, config.byok_rag
        )
        # create or update configuration section providers/vector_io
        ls_config["providers"]["vector_io"] = construct_vector_io_providers_section(
            ls_config, config.byok_rag
        )

    logger.info("Writing Llama Stack configuration into file %s", output_file)

    with open(output_file, "w", encoding="utf-8") as file:
        yaml.dump(ls_config, file, Dumper=YamlDumper, default_flow_style=False)


def construct_vector_dbs_section(
    ls_config: dict[str, Any], byok_rag: list[ByokRag]
) -> list[dict[str, Any]]:
    """Construct vector_dbs section in Llama Stack configuration file."""
    output = []

    # fill-in existing vector_dbs entries
    if "vector_dbs" in ls_config:
        output = ls_config["vector_dbs"]

    # append new vector_dbs entries
    for brag in byok_rag:
        output.append(
            {
                "vector_db_id": brag.vector_db_id,
                "provider_id": "byok_" + brag.vector_db_id,
                "embedding_model": brag.embedding_model,
                "embedding_dimension": brag.embedding_dimension,
            }
        )
    logger.info(
        "Added %s items into vector_dbs section, total items %s",
        len(byok_rag),
        len(output),
    )
    return output


def construct_vector_io_providers_section(
    ls_config: dict[str, Any], byok_rag: list[ByokRag]
) -> list[dict[str, Any]]:
    """Construct providers/vector_io section in Llama Stack configuration file."""
    output = []

    # fill-in existing vector_io entries
    if "vector_io" in ls_config["providers"]:
        output = ls_config["providers"]["vector_io"]

    # append new vector_io entries
    for brag in byok_rag:
        output.append(
            {
                "provider_id": "byok_" + brag.vector_db_id,
                "provider_type": brag.rag_type,
                "config": {
                    "kvstore": {
                        "db_path": ".llama/" + brag.vector_db_id + ".db",
                        "namespace": None,
                        "type": "sqlite",
                    }
                },
            }
        )
    logger.info(
        "Added %s items into providers/vector_io section, total items %s",
        len(byok_rag),
        len(output),
    )
    return output
