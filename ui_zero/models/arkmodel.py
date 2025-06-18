"""Base model class for OpenAI-compatible APIs."""

import os
from typing import Optional

from ..localization import get_text


class ArkModel:
    """Base class for OpenAI-compatible API models."""

    def __init__(
        self,
        model_name: str,
        system_prompt: str = "",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL")

    def __repr__(self):
        api_key_snippet = self.api_key[:8] if self.api_key else None
        return f"ArkModel(model_name={self.model_name}, api_key={api_key_snippet}..., base_url={self.base_url})"

    def __str__(self):
        api_key_snippet = self.api_key[:8] if self.api_key else None
        return f"ArkModel: {self.model_name}\nAPI Key: {api_key_snippet}...\nBase URL: {self.base_url}"

    def run(
        self, user_prompt: str, image: Optional[str] = None
    ):  # pylint: disable=unused-argument
        """Run the model with the given prompt and image."""
        raise NotImplementedError(get_text("arkmodel_run_not_implemented"))
