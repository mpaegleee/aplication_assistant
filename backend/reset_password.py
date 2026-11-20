"""Recuperação offline pelo proprietário da instalação; encerre o aplicativo antes."""

import getpass
from filelock import FileLock, Timeout
from assistant.api import data_directory
from assistant.store import Store


def main():
    store = Store(data_directory())
    lock = FileLock(str(store.directory / "instance.lock"))
    try:
        lock.acquire(timeout=0)
    except Timeout:
        raise SystemExit("Encerre o Application Assistant antes de redefinir a senha.")
    try:
        password = getpass.getpass("Nova senha (mínimo 12 caracteres): ")
        if len(password) < 12 or len(password) > 256:
            raise SystemExit("Senha deve ter entre 12 e 256 caracteres.")
        if password != getpass.getpass("Repita a nova senha: "):
            raise SystemExit("As senhas não coincidem.")
        store.create_password(password, replace=True)
        print("Senha redefinida. Todas as sessões foram encerradas.")
    finally:
        lock.release()


if __name__ == "__main__":
    main()
