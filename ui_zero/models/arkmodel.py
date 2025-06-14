import os
from openai import OpenAI
from pathlib import Path
import base64
from typing import Optional


class ArkModel:
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
        return f"ArkModel(model_name={self.model_name}, api_key={self.api_key[:8]}..., base_url={self.base_url})"

    def __str__(self):
        return f"ArkModel: {self.model_name}\nAPI Key: {self.api_key[:8] if self.api_key else None}...\nBase URL: {self.base_url}"

    def run(self, user_prompt: str, image: Optional[str] = None):
        raise NotImplementedError("The run method should be implemented in subclasses.")
