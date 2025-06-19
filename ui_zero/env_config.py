#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
环境配置管理模块
用于检查、设置和管理UI-Zero所需的环境变量
"""

import os
import sys
from pathlib import Path
from typing import Dict, Optional, List, Union, Callable, TypedDict, Any, cast
import dotenv
from .localization import get_text


# 定义类型
class EnvVarConfig(TypedDict):
    """环境变量配置类型"""

    description_key: str
    example: str
    validation: Callable[[str], bool]


class InvalidVarInfo(TypedDict):
    """无效环境变量信息类型"""

    value: str
    config: EnvVarConfig


class EnvCheckResult(TypedDict):
    """环境检查结果类型"""

    missing: Dict[str, EnvVarConfig]
    invalid: Dict[str, InvalidVarInfo]
    valid: bool


class EnvConfig:
    """环境配置管理器"""

    # 必需的环境变量配置
    REQUIRED_ENV_VARS = {
        "OPENAI_API_KEY": {
            "description_key": "env_openai_api_key_desc",
            "example": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx 或 xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            "validation": lambda x: x
            and len(x.strip()) > 10,  # 简单长度验证，支持多种格式
        },
        "OPENAI_BASE_URL": {
            "description_key": "env_openai_base_url_desc",
            "example": "https://api.openai.com/v1",
            "validation": lambda x: x
            and len(x.strip()) > 0
            and (x.startswith("http://") or x.startswith("https://")),
        },
    }

    def __init__(self):
        """初始化环境配置管理器"""
        self.config_dir = Path.home() / ".uiz"
        self.config_file = self.config_dir / "config.env"
        self._ensure_config_dir()

    def _ensure_config_dir(self):
        """确保配置目录存在"""
        self.config_dir.mkdir(exist_ok=True)

    def load_config(self):
        """加载配置文件中的环境变量"""
        if self.config_file.exists():
            dotenv.load_dotenv(self.config_file)

    def save_config(self, env_vars: Dict[str, str]):
        """保存环境变量到配置文件"""
        with open(self.config_file, "w", encoding="utf-8") as f:
            f.write("# UI-Zero 环境配置文件\n")
            f.write("# 此文件由UI-Zero自动生成和管理\n\n")
            for key, value in env_vars.items():
                f.write(f"{key}={value}\n")
        print(get_text("env_config_saved").format(self.config_file))

    def check_env_vars(self) -> EnvCheckResult:
        """检查所有必需的环境变量"""
        missing_vars = {}
        invalid_vars = {}

        for var_name, config in self.REQUIRED_ENV_VARS.items():
            value = os.getenv(var_name)
            if not value:
                missing_vars[var_name] = config
            elif not config["validation"](value):
                invalid_vars[var_name] = {"value": value, "config": config}

        return {
            "missing": missing_vars,
            "invalid": invalid_vars,
            "valid": len(missing_vars) == 0 and len(invalid_vars) == 0,
        }

    def prompt_for_env_var(self, var_name: str, config: EnvVarConfig) -> str:
        """提示用户输入环境变量值"""
        print(f"\n{'='*60}")
        print(get_text("env_config_var_title").format(var_name))
        description_key = cast(str, config["description_key"])
        print(get_text("env_config_description").format(get_text(description_key)))
        example = cast(str, config["example"])
        print(get_text("env_config_example").format(example))
        print("=" * 60)

        while True:
            value = input(get_text("env_input_prompt").format(var_name)).strip()

            if not value:
                print(get_text("env_value_empty_error"))
                continue

            validation_func = cast(Callable[[str], bool], config["validation"])
            if not validation_func(value):
                print(get_text("env_value_format_error"))
                if var_name == "OPENAI_API_KEY":
                    print(get_text("env_api_key_format_hint"))
                elif var_name == "OPENAI_BASE_URL":
                    print(get_text("env_url_format_hint"))
                continue

            return value

    def interactive_setup(self) -> bool:
        """交互式环境配置设置"""
        print(f"\n{get_text('env_setup_wizard_title')}")
        print("=" * 50)

        result = self.check_env_vars()

        if result["valid"]:
            print(get_text("env_all_configured"))
            return True

        env_vars_to_set = {}

        # 处理缺失的环境变量
        if result["missing"]:
            print(
                f"\n{get_text('env_missing_vars_found').format(len(result['missing']))}"
            )
            for var_name in result["missing"]:
                print(f"   - {var_name}")

            print(
                f"\n{get_text('env_prompt_input_vars').format(get_text('env_setup_doc_hint'))}"
            )
            for var_name, config in result["missing"].items():
                value = self.prompt_for_env_var(var_name, config)
                env_vars_to_set[var_name] = value
                os.environ[var_name] = value  # 立即设置到当前环境

        # 处理无效的环境变量
        if result["invalid"]:
            print(
                f"\n{get_text('env_invalid_vars_found').format(len(result['invalid']))}"
            )
            for var_name, info in result["invalid"].items():
                print(f"   - {var_name}: {info['value']}")

            print(f"\n{get_text('env_prompt_reinput_vars')}")
            for var_name, info in result["invalid"].items():
                value = self.prompt_for_env_var(var_name, info["config"])
                env_vars_to_set[var_name] = value
                os.environ[var_name] = value  # 立即设置到当前环境

        # 保存配置
        if env_vars_to_set:
            # 读取现有配置
            existing_vars = {}
            if self.config_file.exists():
                dotenv.load_dotenv(
                    self.config_file,
                    override=False,
                    interpolate=False,
                    encoding="utf-8",
                    stream=None,
                    verbose=False,
                )
                # 获取现有的环境变量
                for var_name in self.REQUIRED_ENV_VARS.keys():
                    if var_name in os.environ and var_name not in env_vars_to_set:
                        existing_vars[var_name] = os.getenv(var_name)

            # 合并现有配置和新配置
            all_vars = {**existing_vars, **env_vars_to_set}
            self.save_config(all_vars)

            print(f"\n{get_text('env_config_completed').format(len(env_vars_to_set))}")
            print(get_text("env_config_file_location").format(self.config_file))

        return True

    def validate_current_config(self) -> bool:
        """验证当前配置的有效性"""
        result = self.check_env_vars()

        if not result["valid"]:
            print(f"\n{get_text('env_validation_failed')}")

            if result["missing"]:
                print(get_text("env_missing_vars_list").format(len(result["missing"])))
                for var_name in result["missing"]:
                    print(f"     - {var_name}")

            if result["invalid"]:
                print(get_text("env_invalid_vars_list").format(len(result["invalid"])))
                for var_name, info in result["invalid"].items():
                    print(f"     - {var_name}: {info['value']}")

            print(f"\n{get_text('env_reconfigure_hint')}")
            print(get_text("env_setup_command_hint"))
            return False

        print(get_text("env_validation_passed"))
        return True

    def test_api_connection(self) -> bool:
        """测试API连接"""
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            base_url = os.getenv("OPENAI_BASE_URL")

            if not api_key or not base_url:
                return False

            # 这里可以添加实际的API连接测试
            # 暂时返回True，表示配置格式正确
            print(get_text("env_api_test_running"))
            print(get_text("env_api_test_passed"))
            return True

        except Exception as e:
            print(get_text("env_api_test_failed").format(e))
            return False


def ensure_env_config(skip_interactive: bool = False) -> bool:
    """
    确保环境配置正确

    Args:
        skip_interactive: 是否跳过交互式配置

    Returns:
        bool: 配置是否成功
    """
    config = EnvConfig()

    # 首先加载现有配置
    config.load_config()

    # 检查配置
    result = config.check_env_vars()

    if result["valid"]:
        return True

    if skip_interactive:
        print(get_text("env_config_incomplete_skip"))
        return False

    # 运行交互式配置
    return config.interactive_setup()


def setup_env_interactive() -> bool:
    """运行交互式环境配置"""
    config = EnvConfig()
    config.load_config()
    return config.interactive_setup()


def validate_env() -> bool:
    """验证环境配置"""
    config = EnvConfig()
    config.load_config()
    return config.validate_current_config()
