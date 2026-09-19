import argparse
import getpass
import sys
from pathlib import Path

from app.core.database import SessionLocal
from app.modules.auth.security import BCRYPT_MAX_BYTES, hash_password
from app.modules.users.model import User, UserRole
from app.modules.users.repository import UserRepository

MIN_PASSWORD_LENGTH = 8


def read_password(provided: str | None) -> str:
    if provided:
        return provided
    password = getpass.getpass("Senha: ")
    if password != getpass.getpass("Confirme a senha: "):
        sys.exit("As senhas não conferem.")
    return password


def create_user(args: argparse.Namespace) -> None:
    password = read_password(args.password)
    if len(password) < MIN_PASSWORD_LENGTH:
        sys.exit(
            f"A senha precisa ter pelo menos {MIN_PASSWORD_LENGTH} caracteres.")
    if len(password.encode("utf-8")) > BCRYPT_MAX_BYTES:
        sys.exit(f"A senha pode ter no máximo {BCRYPT_MAX_BYTES} bytes.")

    with SessionLocal() as db:
        users = UserRepository(db)
        for login in (args.username, args.email):
            if users.get_by_login(login) is not None:
                sys.exit(f"Já existe um usuário com '{login}'.")

        user = users.add(
            User(
                username=args.username.strip(),
                email=args.email.strip().lower(),
                full_name=args.full_name,
                hashed_password=hash_password(password),
                role=UserRole.ADMIN if args.admin else UserRole.USER,
                is_active=True,
            )
        )
        print(
            f"Usuário '{user.username}' criado (id={user.id}, perfil={user.role.value}).")


SCHEMA_FILE = Path(__file__).resolve().parent.parent / "schema.graphql"


def export_graphql_schema(_: argparse.Namespace) -> None:
    from app.core.graphql import schema  # import tardio: só este comando precisa

    SCHEMA_FILE.write_text(str(schema) + "\n", encoding="utf-8", newline="\n")
    print(f"Schema GraphQL exportado para {SCHEMA_FILE}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)

    create = commands.add_parser(
        "create-user", help="Cria um usuário para fazer login")
    create.add_argument("--username", required=True)
    create.add_argument("--email", required=True)
    create.add_argument("--full-name", default=None)
    create.add_argument("--password", default=None,
                        help="Omitir para digitar com segurança")
    create.add_argument("--admin", action="store_true",
                        help="Cria com perfil ADMIN")
    create.set_defaults(func=create_user)

    export = commands.add_parser(
        "export-graphql-schema", help="Grava o schema GraphQL em backend/schema.graphql")
    export.set_defaults(func=export_graphql_schema)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
