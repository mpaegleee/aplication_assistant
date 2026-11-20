import os, json, sqlite3, secrets, hashlib, hmac
from pathlib import Path
from datetime import datetime, timezone, timedelta
from contextlib import contextmanager
from cryptography.fernet import Fernet


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        try:
            self.directory.chmod(0o700)
        except OSError:
            pass
        key = self.directory / "vault.key"
        if not key.exists():
            # Never regenerate a missing key for an existing database.
            if (self.directory / "assistant.sqlite3").exists():
                raise RuntimeError(
                    "Chave de dados ausente. Restaure vault.key do backup."
                )
            fd = os.open(key, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(Fernet.generate_key())
        self.cipher = Fernet(key.read_bytes())
        with self.connection() as c:
            c.execute("PRAGMA journal_mode=WAL")
            version = c.execute("PRAGMA user_version").fetchone()[0]
            if version > 1:
                raise RuntimeError(
                    "Banco criado por versão mais nova. Atualize o aplicativo."
                )
            c.executescript("""
            CREATE TABLE IF NOT EXISTS objects(kind TEXT, id TEXT, data BLOB NOT NULL, PRIMARY KEY(kind,id));
            CREATE TABLE IF NOT EXISTS auth(id INTEGER PRIMARY KEY CHECK(id=1), salt TEXT NOT NULL, hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, expires TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS counters(day TEXT, kind TEXT, value INTEGER NOT NULL, PRIMARY KEY(day,kind));
            PRAGMA user_version=1;
            """)

    @contextmanager
    def connection(self):
        c = sqlite3.connect(self.directory / "assistant.sqlite3", timeout=30)
        try:
            with c:
                yield c
        finally:
            c.close()

    def encode(self, v):
        return self.cipher.encrypt(json.dumps(v, ensure_ascii=False).encode())

    def decode(self, v):
        return json.loads(self.cipher.decrypt(v))

    def get(self, kind, id="current", default=None):
        with self.connection() as c:
            row = c.execute(
                "SELECT data FROM objects WHERE kind=? AND id=?", (kind, id)
            ).fetchone()
        return self.decode(row[0]) if row else default

    def put(self, kind, value, id="current"):
        with self.connection() as c:
            c.execute(
                "INSERT INTO objects VALUES(?,?,?) ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data",
                (kind, id, self.encode(value)),
            )
        return value

    def insert(self, kind, value, id):
        with self.connection() as c:
            r = c.execute(
                "INSERT OR IGNORE INTO objects VALUES(?,?,?)",
                (kind, id, self.encode(value)),
            )
            return r.rowcount == 1

    def all(self, kind):
        with self.connection() as c:
            rows = c.execute(
                "SELECT data FROM objects WHERE kind=? ORDER BY rowid DESC", (kind,)
            ).fetchall()
        return [self.decode(r[0]) for r in rows]

    def event(self, job_id, message):
        self.put(
            "events",
            {
                "id": secrets.token_hex(8),
                "job_id": job_id,
                "message": message,
                "at": now(),
            },
            secrets.token_hex(12),
        )

    def count(self, kind, day):
        with self.connection() as c:
            r = c.execute(
                "SELECT value FROM counters WHERE day=? AND kind=?", (day, kind)
            ).fetchone()
        return r[0] if r else 0

    def reserve(self, kind, day, limit):
        with self.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute("INSERT OR IGNORE INTO counters VALUES(?,?,0)", (day, kind))
            return (
                c.execute(
                    "UPDATE counters SET value=value+1 WHERE day=? AND kind=? AND value<?",
                    (day, kind, limit),
                ).rowcount
                == 1
            )

    def configured(self):
        with self.connection() as c:
            return bool(c.execute("SELECT 1 FROM auth").fetchone())

    def create_password(self, password, replace=False):
        salt = secrets.token_hex(16)
        digest = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1
        ).hex()
        with self.connection() as c:
            if replace:
                c.execute("DELETE FROM sessions")
                c.execute("INSERT OR REPLACE INTO auth VALUES(1,?,?)", (salt, digest))
            else:
                c.execute("INSERT INTO auth VALUES(1,?,?)", (salt, digest))

    def login(self, password):
        with self.connection() as c:
            row = c.execute("SELECT salt,hash FROM auth").fetchone()
        if not row:
            return None
        digest = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(row[0]), n=16384, r=8, p=1
        ).hex()
        if not hmac.compare_digest(digest, row[1]):
            return None
        token = secrets.token_urlsafe(32)
        with self.connection() as c:
            c.execute("DELETE FROM sessions WHERE expires<?", (now(),))
            c.execute(
                "INSERT INTO sessions VALUES(?,?)",
                (
                    hashlib.sha256(token.encode()).hexdigest(),
                    (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat(),
                ),
            )
        return token

    def authenticated(self, token):
        if not token:
            return False
        with self.connection() as c:
            return bool(
                c.execute(
                    "SELECT 1 FROM sessions WHERE token=? AND expires>?",
                    (hashlib.sha256(token.encode()).hexdigest(), now()),
                ).fetchone()
            )

    def logout(self, token):
        with self.connection() as c:
            c.execute(
                "DELETE FROM sessions WHERE token=?",
                (hashlib.sha256(token.encode()).hexdigest(),),
            )
