from __future__ import annotations

from keepr.config import DatabaseConfig
from keepr.engines.base import DatabaseEngine


class PostgresEngine(DatabaseEngine):
    name = "postgres"

    def build_dump_command(self, config: DatabaseConfig) -> str:
        if config.docker:
            return self._build_docker_dump(config)

        binary = config.dump_path or "pg_dump"
        parts = [binary, f"-h {config.host}", f"-p {config.port}", f"-U {config.user}"]

        if config.format == "sql":
            parts.append("-Fp")  # Plain SQL format
        else:
            parts.append("-Fc")  # Custom format (compressed)

        if config.extra_args:
            parts.append(config.extra_args)
        parts.append(config.name)
        return " ".join(parts)

    def build_restore_command(self, config: DatabaseConfig, backup_path: str) -> str:
        if config.docker:
            return self._build_docker_restore(config, backup_path)

        if config.format == "sql":
            # SQL format needs gunzip + psql
            psql = "psql"
            parts = [
                f"gunzip -c {backup_path} |",
                psql,
                f"-h {config.host}",
                f"-p {config.port}",
                f"-U {config.user}",
                f"-d {config.name}",
            ]
        else:
            parts = [
                "pg_restore",
                f"-h {config.host}",
                f"-p {config.port}",
                f"-U {config.user}",
                f"-d {config.name}",
                "--no-owner",
                "--clean",
                "--if-exists",
                backup_path,
            ]
        return " ".join(parts)

    def get_file_extension(self, config: DatabaseConfig) -> str:
        if config.format == "sql":
            return ".sql.gz"
        return ".dump"

    @property
    def needs_compression(self, config: DatabaseConfig | None = None) -> bool:
        if config and config.format == "sql":
            return True
        return False

    def needs_compression_for(self, config: DatabaseConfig) -> bool:
        return config.format == "sql"

    def get_env(self, config: DatabaseConfig) -> dict[str, str]:
        env = {}
        if config.password:
            env["PGPASSWORD"] = config.password
        return env

    # ── Docker mode ──────────────────────────────────────────

    def _build_docker_dump(self, config: DatabaseConfig) -> str:
        """pg_dump inside the container; stdout streams back to host."""
        exec_parts = self._docker_exec_prefix(config, interactive=False)
        dump = ["pg_dump", f"-U {config.user}"]
        dump.append("-Fp" if config.format == "sql" else "-Fc")
        if config.extra_args:
            dump.append(config.extra_args)
        dump.append(config.name)
        return " ".join(exec_parts + dump)

    def _build_docker_restore(self, config: DatabaseConfig, backup_path: str) -> str:
        """Stream the backup from host into container's pg_restore/psql via stdin."""
        exec_parts = self._docker_exec_prefix(config, interactive=True)
        if config.format == "sql":
            tool = ["psql", f"-U {config.user}", f"-d {config.name}"]
            return f"gunzip -c {backup_path} | {' '.join(exec_parts + tool)}"
        tool = [
            "pg_restore",
            f"-U {config.user}",
            f"-d {config.name}",
            "--no-owner",
            "--clean",
            "--if-exists",
        ]
        return f"cat {backup_path} | {' '.join(exec_parts + tool)}"

    @staticmethod
    def _docker_exec_prefix(config: DatabaseConfig, interactive: bool) -> list[str]:
        parts = ["docker", "exec"]
        if interactive:
            parts.append("-i")
        if config.password:
            # Forward PGPASSWORD from host env (set by Executor) into the container
            parts.append("-e PGPASSWORD")
        if config.docker.user:
            parts.append(f"--user {config.docker.user}")
        parts.append(config.docker.container)
        return parts
