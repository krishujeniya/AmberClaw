# ruff: noqa: PLC0415
from typing import Any

from amberclaw.terminal.base import BaseTerminalBackend


class BackendFactory:
    """Factory to dynamically instantiate terminal execution backends."""

    @staticmethod
    def create_backend(
        backend_type: str,
        workspace_dir: str,
        **kwargs: Any,
    ) -> BaseTerminalBackend:
        """
        Instantiate a terminal execution backend based on the type.

        Args:
            backend_type: One of 'local', 'docker', 'ssh', 'daytona', 'singularity', 'modal'.
            workspace_dir: Directory context for execution.
            **kwargs: Backend-specific arguments:
                - image (str) for docker and singularity backends.
                - host (str), port (int), username (str), password (str),
                  key_filename (str), agent_forwarding (bool) for SSH backend.
                - api_key (str), api_url (str), target (str), create_kwargs (dict) for Daytona backend.
                - app_name (str) for Modal backend.
        """
        backend_type = backend_type.lower()
        if backend_type == "local":
            from amberclaw.terminal.local import LocalTerminalBackend

            return LocalTerminalBackend(workspace_dir=workspace_dir)

        if backend_type == "docker":
            from amberclaw.terminal.docker import DockerTerminalBackend

            image = kwargs.get("image", "python:3.11-slim")
            return DockerTerminalBackend(workspace_dir=workspace_dir, image=image)

        if backend_type == "ssh":
            from amberclaw.terminal.ssh import SSHTerminalBackend

            return SSHTerminalBackend(
                workspace_dir=workspace_dir,
                host=kwargs.get("host", "localhost"),
                port=kwargs.get("port", 22),
                username=kwargs.get("username", "root"),
                password=kwargs.get("password"),
                key_filename=kwargs.get("key_filename"),
                agent_forwarding=kwargs.get("agent_forwarding", True),
            )

        if backend_type == "daytona":
            from amberclaw.terminal.daytona import (
                DaytonaTerminalBackend,
            )

            return DaytonaTerminalBackend(
                workspace_dir=workspace_dir,
                api_key=kwargs.get("api_key"),
                api_url=kwargs.get("api_url"),
                target=kwargs.get("target"),
                create_kwargs=kwargs.get("create_kwargs"),
            )

        if backend_type == "singularity":
            from amberclaw.terminal.singularity import (
                SingularityTerminalBackend,
            )

            image = kwargs.get("image", "docker://python:3.11-slim")
            return SingularityTerminalBackend(
                workspace_dir=workspace_dir,
                image=image,
            )

        if backend_type == "modal":
            from amberclaw.terminal.modal import (
                ModalTerminalBackend,
            )

            app_name = kwargs.get("app_name", "amberclaw-sandbox")
            return ModalTerminalBackend(
                workspace_dir=workspace_dir,
                app_name=app_name,
            )

        raise ValueError(f"Unknown terminal backend type: '{backend_type}'")
