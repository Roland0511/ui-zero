# UI-Zero

**English** | [中文](https://github.com/Roland0511/ui-zero/blob/main/README_zh.md)

A Python library for AI-powered UI automation testing. This library provides command-line tools for automated UI testing using computer vision and AI models.

## Features

- Android device automation via ADB
- AI-powered UI element recognition and interaction
- Command-line interface for test execution
- Support for multiple AI models (Doubao, Ark, etc.)
- Comprehensive screenshot and interaction capabilities
- **Internationalization Support** - Auto-detects system language with Chinese/English interface
- **Professional Localization** - Uses gettext for industry-standard internationalization

## Installation

Using uv (recommended):
```bash
uv add ui-zero
```

Or using pip:
```bash
pip install ui-zero
```

## Development Installation

```bash
# Clone the repository
git clone https://github.com/Roland0511/ui-zero.git
cd ui-zero

# Install development dependencies with uv
uv sync --dev

# Or using pip
pip install -e ".[dev]"
```

## Setup Environment Variables

This library uses ByteDance's [UI-TARS](https://github.com/bytedance/UI-TARS) model for AI-powered UI recognition. 
Follow the [deployment guide](https://juniper-switch-f10.notion.site/UI-TARS-Model-Deployment-Guide-17b5350241e280058e98cea60317de71) to deploy the model and obtain an API key.

> For Chinese users, see [UI-TARS 模型部署教程](https://bytedance.sg.larkoffice.com/docx/TCcudYwyIox5vyxiSDLlgIsTgWf).

After deployment, set the following environment variables in your system:
```bash
# Set the API key in your environment
export OPENAI_API_KEY="your_api_key_here"
export OPENAI_BASE_URL="your_api_base_url_here"
```

## Environment Requirements

### For Computer
- Python 3.10+
- Android SDK with ADB installed
- Connected Android device with USB debugging enabled

### For Android Device
- Android 8.0+ (API level 26+)
- USB debugging enabled
- [ADBKeyboard](https://github.com/senzhk/ADBKeyBoard) installed for text input support

## Command Line Usage

After installation, you can use the `uiz` command:

```bash
# Run with test case file
uiz --testcase test_case.json

# Run with direct commands
uiz --command "find and click settings icon"

# List available devices
uiz --list-devices

# Use specific device (recommended when multiple devices are connected)
uiz --device DEVICE_ID --command "find and click settings icon"

# Enable debug mode
uiz --debug --command "search for Wi-Fi settings, then click"

# Disable history feature
uiz --no-history --command "open app"

# Show help information
uiz --help
```

## Python API Usage

```python
from ui_zero import AndroidAgent, ADBTool

# Initialize ADB and agent
adb_tool = ADBTool()
agent = AndroidAgent(adb_tool)

# Run a test step
result = agent.run("find search bar and type 'hello world'")

# Execute with callbacks
def on_screenshot(img_bytes):
    print(f"Screenshot size: {len(img_bytes)} bytes")

def on_action(prompt, action):
    print(f"Executing action: {action.action}")

result = agent.run(
    "click settings button",
    screenshot_callback=on_screenshot,
    preaction_callback=on_action
)
```

## Internationalization Features

UI-Zero supports automatic localization based on system language:

### Automatic Language Detection
The system automatically detects the following environment variables and sets the appropriate language:
- `LANG`
- `LC_ALL`
- `LC_MESSAGES`

### Manual Language Setting
```python
from ui_zero.localization import set_language

# Set to Chinese
set_language('zh_CN')

# Set to English
set_language('en_US')
```

### Supported Languages
- Chinese (Simplified): `zh_CN`
- English (US): `en_US`

## Development Guide

### Code Quality Checks

```bash
# Code formatting
uv run black ui_zero/

# Import sorting
uv run isort ui_zero/

# Type checking
uv run mypy ui_zero/

# Linting
uv run flake8 ui_zero/
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=ui_zero

# Run localization tests
uv run pytest tests/test_localization.py -v
```

### Translation Management

Compile translation files:
```bash
# Compile all .po files to .mo files
uv run python scripts/compile_translations.py
```

Manual localization testing:
```bash
# Run localization manual tests
uv run python tests/test_localization.py --manual
```

## Project Structure

```
ui_zero/
├── __init__.py           # Package initialization
├── cli.py               # Command line interface
├── agent.py             # Android automation agent
├── adb.py               # ADB tool class
├── localization.py      # Internationalization manager
├── locale/              # Translation files directory
│   ├── messages.pot     # Translation template
│   ├── zh_CN/LC_MESSAGES/
│   │   ├── ui_zero.po   # Chinese translation source
│   │   └── ui_zero.mo   # Chinese binary file
│   └── en_US/LC_MESSAGES/
│       ├── ui_zero.po   # English translation source
│       └── ui_zero.mo   # English binary file
└── models/              # AI model integrations
    ├── __init__.py
    ├── arkmodel.py      # Ark model base class
    └── doubao_ui_tars.py # Doubao UI-TARS model
```

## Test Case Format

### JSON Format
Create a `test_case.json` file:

```json
[
    "find and click settings icon",
    "scroll to bottom",
    "click about phone",
    "go back"
]
```

### YAML Format (Recommended)
Create a `test_case.yaml` file for more advanced test scenarios:

```yaml
android:
  # Device ID, optional, defaults to first connected device
  deviceId: <device-id>
tasks:
  - name: <task-name>
    continueOnError: <boolean> # Optional, whether to continue on error, defaults to false
    flow:
      # Execute an interaction, `ai` is shorthand for `aiAction`
      - ai: <prompt>

      # This usage is the same as `ai`
      - aiAction: <prompt>

      # Wait for a condition to be met, with timeout (ms, optional, defaults to 30000)
      - aiWaitFor: <prompt>
        timeout: <ms>

      # Execute an assertion
      - aiAssert: <prompt>
        errorMessage: <error-message> # Optional, error message to print when assertion fails

      # Wait for a certain time (milliseconds)
      - sleep: <ms>

  - name: <another-task-name>
    flow:
      # ...
```

For complete examples, see [`test_case.example.yaml`](test_case.example.yaml) in the project root.

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `ARK_API_KEY` | UI-TARS model API key | `your_api_key_here` |
| `OPENAI_API_KEY` | OpenAI compatible API key | `sk-...` |
| `OPENAI_BASE_URL` | OpenAI compatible API base URL | `https://api.openai.com/v1` |
| `LANG` | System language (auto-detected) | `en_US.UTF-8` |

## Troubleshooting

### Common Issues

1. **ADB command not available**
   ```bash
   # Ensure Android SDK is installed and added to PATH
   export PATH=$PATH:$ANDROID_HOME/platform-tools
   ```

2. **Device connection issues**
   ```bash
   # Check device connection
   adb devices
   
   # Restart ADB service
   adb kill-server && adb start-server
   ```

3. **Multiple devices detected**
   - When multiple devices are connected, the tool automatically selects the first device
   - Use `--device DEVICE_ID` to specify a particular device to avoid ambiguity
   - Use `--list-devices` to see all available devices

4. **API key issues**
   ```bash
   # Ensure environment variable is set
   echo $ARK_API_KEY
   ```

5. **Text input issues**
   - Ensure ADBKeyboard app is installed on device
   - Enable ADBKeyboard as input method in device settings

## Contributing

Contributions are welcome! Please see the [Contributing Guide](CONTRIBUTING.md) for details.

## License

MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- Issue Reports: [GitHub Issues](https://github.com/Roland0511/ui-zero/issues)
- Documentation: [Project Documentation](https://github.com/Roland0511/ui-zero#readme)
- Repository: [GitHub](https://github.com/Roland0511/ui-zero)