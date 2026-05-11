from __future__ import annotations

from keepr.config import DatabaseConfig
from keepr.engines.base import DatabaseEngine


class MySQLEngine(DatabaseEngine):
    name = "mysql"

    def needs_compression_for(self, config: DatabaseConfig) -> bool:
        return True

    def build_dump_command(self, config: DatabaseConfig) -> str:
        if config.docker:
            return self._build_docker_dump(config)

        binary = config.dump_path or "mysqldump"
        parts = [
            binary,
            f"-h {config.host}",
            f"-P {config.port}",
            f"-u {config.user}",
            "--single-transaction",
            "--routines",
            "--triggers",
        ]
        if config.password:
            parts.append(f"-p'{config.password}'")
        if config.extra_args:
            parts.append(config.extra_args)
        parts.append(config.name)
        return " ".join(parts)

    def build_restore_command(self, config: DatabaseConfig, backup_path: str) -> str:
        if config.docker:
            return self._build_docker_restore(config, backup_path)

        parts = [
            f"gunzip -c {backup_path} |",
            "mysql",
            f"-h {config.host}",
            f"-P {config.port}",
            f"-u {config.user}",
        ]
        if config.password:
            parts.append(f"-p'{config.password}'")
        parts.append(config.name)
        return " ".join(parts)

    def get_file_extension(self, config: DatabaseConfig) -> str:
        return ".sql.gz"

    def get_env(self, config: DatabaseConfig) -> dict[str, str]:
        # Only use MYSQL_PWD env in docker mode (avoid `-p` + env warning otherwise)
        if config.docker and config.password:
            return {"MYSQL_PWD": config.password}
        return {}

    # ── Docker mode ──────────────────────────────────────────

    def _build_docker_dump(self, config: DatabaseConfig) -> str:
        exec_parts = self._docker_exec_prefix(config, interactive=False)
        dump = [
            "mysqldump",
            f"-u {config.user}",
            "--single-transaction",
            "--routines",
            "--triggers",
        ]
        if config.extra_args:
            dump.append(config.extra_args)
        dump.append(config.name)
        return " ".join(exec_parts + dump)

    def _build_docker_restore(self, config: DatabaseConfig, backup_path: str) -> str:
        exec_parts = self._docker_exec_prefix(config, interactive=True)
        tool = ["mysql", f"-u {config.user}", config.name]
        return f"gunzip -c {backup_path} | {' '.join(exec_parts + tool)}"

    @staticmethod
    def _docker_exec_prefix(config: DatabaseConfig, interactive: bool) -> list[str]:
        parts = ["docker", "exec"]
        if interactive:
            parts.append("-i")
        if config.password:
            parts.append("-e MYSQL_PWD")
        if config.docker.user:
            parts.append(f"--user {config.docker.user}")
        parts.append(config.docker.container)
        return parts
