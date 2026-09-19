"""O schema GraphQL é o contrato com o frontend: mudou, tem que atualizar o arquivo."""

from app.cli import SCHEMA_FILE
from app.core.graphql import schema


def test_schema_file_is_up_to_date() -> None:
    assert SCHEMA_FILE.read_text(encoding="utf-8") == str(schema) + "\n", (
        "O schema GraphQL mudou. Rode `python -m app.cli export-graphql-schema` "
        "e versione o backend/schema.graphql atualizado."
    )
