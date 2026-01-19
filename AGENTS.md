# Guidelines for AI Agents

This file provides guidance to any AI agents when working with code in this repository.

## Project Overview

UI-Zero is an AI-powered UI automation testing library for mobile devices. It uses ByteDance's UI-TARS model for computer vision-based UI element recognition and interaction. The project supports both command-line interface and Python API usage for automated UI testing on Android and (via Appium) iOS.

## Development Commands

### Package Management
- `uv sync --dev` - Install all dependencies including development tools
- `uv add <package>` - Add new dependency
- `uv run <command>` - Run commands in virtual environment

### Code Quality
- `uv run black ui_zero/` - Format code with Black
- `uv run isort ui_zero/` - Sort imports
- `uv run mypy ui_zero/` - Type checking
- `uv run flake8 ui_zero/` - Linting

### Testing
- `uv run pytest` - Run all tests
- `uv run pytest --cov=ui_zero` - Run tests with coverage
- `uv run pytest tests/test_localization.py -v` - Run specific test file

### Localization
- `uv run python scripts/compile_translations.py` - Compile .po files to .mo files
- `uv run python tests/test_localization.py --manual` - Manual localization testing

### Application Usage
- `uiz --help` - Show help information
- `uiz --testcase test_case.yaml` - Run YAML test case
- `uiz --command "find and click settings"` - Run single command
- `uiz --list-devices` - List connected Android/iOS devices
- `uiz --setup-env` - Interactive environment setup
- `uiz --validate-env` - Validate environment configuration
- `uiz --serve` - Start API server with REST and WebSocket support
- `uiz --serve --host 127.0.0.1 --port 9000` - Start server on custom host/port
- `uiz --serve --log-level debug` - Start server with a specific log level
- `uiz --testcase tests/demo.yaml --output run.json` - Execute a suite and export results
- `uiz --legacy` - Use legacy model (doubao-1-5-ui-tars-250428)
- `uiz --reasoning-effort low|medium|high` - Set model reasoning effort (only for new model)

## Architecture

### Core Components

#### CLI Module (`ui_zero/cli.py`)
- Main entry point for command-line interface
- Handles argument parsing and test case execution
- Supports both JSON and YAML test case formats
- Manages environment validation and device selection
- Integrates with UI display system for progress tracking

#### Agent Module (`ui_zero/agent.py`)
- `AndroidAgent` class - Main automation agent
- Coordinates between ADB tool and AI model
- Maintains action history for context
- Supports timeout and iteration limits
- Handles screenshot capture and action execution

#### Device Driver Module (`ui_zero/device_driver.py`)
- Abstracts device operations behind `DeviceDriver`
- Provides Android implementation via existing `ADBTool`
- Adds optional iOS driver backed by `appium-python-client`
- Supplies factory helpers to select platform (`UIZ_DEVICE_PLATFORM`)
- Lists connected devices for both Android and iOS

#### ADB Module (`ui_zero/adb.py`)
- `ADBTool` class - Android Debug Bridge wrapper
- Device management and selection
- Screen capture, touch simulation, text input
- App lifecycle management
- Hardware key simulation

#### AI Models (`ui_zero/models/`)
- `DoubaoUITarsModel` - ByteDance UI-TARS integration. Supports multiple model versions (`doubao-seed-1-8-251228` as default, `doubao-1-5-ui-tars-250428` as legacy) and configurable `reasoning_effort` for the seed model.
- `ArkModel` - Base class for AI models
- Handles image processing and coordinate conversion
- Parses model output into structured actions

#### Environment Configuration (`ui_zero/env_config.py`)
- `EnvConfig` class - Environment variable management
- Interactive setup wizard for API keys
- Validation and testing of configuration
- Persistent storage in `~/.uiz/config.env`

#### API Server (`ui_zero/server.py`)
- `FastAPI` application with REST endpoints
- WebSocket support for live execution feedback
- Device management and status API
- Test case execution via HTTP requests
- Real-time progress updates through WebSocket connections

### Data Flow

1. CLI parses arguments and loads test cases (JSON/YAML)
2. Environment validation ensures API keys are configured
3. ADB tool connects to Android device
4. AndroidAgent executes test steps in loop:
   - Take screenshot
   - Send to UI-TARS model with prompt
   - Parse model response into ActionOutput
   - Execute action via ADB
   - Update UI progress display

### Test Case Formats

#### YAML Format (Recommended)
```yaml
android:
  deviceId: <device-id>  # Optional
tasks:
  - name: <task-name>
    continueOnError: <boolean>  # Optional
    flow:
      - ai: <prompt>  # AI action
      - aiWaitFor: <condition>  # Wait for condition
        timeout: <ms>  # Optional
      - aiAssert: <condition>  # Assertion
        errorMessage: <message>  # Optional
      - sleep: <ms>  # Wait duration
```

#### JSON Format
```json
[
  "find and click settings icon",
  "scroll to bottom",
  "click about phone"
]
```

### Internationalization

The project uses GNU gettext for internationalization:
- Message catalogs in `ui_zero/locale/`
- Supports Chinese (zh_CN) and English (en_US)
- `get_text()` function for translatable strings
- Auto-detection based on system locale

### Environment Variables

Required for AI model access:
- `OPENAI_API_KEY` - API key for UI-TARS model
- `OPENAI_BASE_URL` - Base URL for API endpoint
- `UIZ_DEVICE_PLATFORM` - Target platform (`android` default, `ios` to use Appium driver)
- `UIZ_IOS_APPIUM_SERVER` - Override Appium server endpoint
- `UIZ_IOS_DEVICE_NAME`, `UIZ_IOS_PLATFORM_VERSION`, `UIZ_IOS_DEVICE_UDID`, `UIZ_IOS_BUNDLE_ID`, `UIZ_IOS_AUTOMATION_NAME` - iOS desired capabilities when using Appium

## Development Guidelines

### Code Style
- Follow Black formatting (line length 88)
- Use isort for import organization
- Enable mypy strict mode for type checking
- Follow flake8 linting rules

### Testing Requirements
- Use pytest for all tests
- Maintain test coverage
- Include localization tests
- Test CLI integration scenarios

### File Organization
- Keep modules focused and single-purpose
- Use type hints consistently
- Implement proper error handling with localized messages
- Follow existing patterns for new features

### Device Requirements
- Android 8.0+ (API level 26+)
- USB debugging enabled
- Optional: iOS device with Appium server available when `UIZ_DEVICE_PLATFORM=ios`
- ADBKeyboard app installed for text input

### Common Patterns
- Use `get_logger()` for logging with module-specific loggers
- Implement proper cleanup in try/finally blocks
- Use `get_text()` for all user-facing messages
- Handle multiple device scenarios gracefully

### Logging
- Centralized configuration in `ui_zero/logging_config.py` with log files under `~/.uiz/log/`
- Prefer `get_logger("component")` to create child loggers aligned with CLI log level selection
- Adjust verbosity using CLI `--log-level` flag or by calling `configure_logging()` in code

## API Server Usage

### Starting the Server
```bash
# Start with default settings (0.0.0.0:8000)
uiz --serve

# Start on specific host and port
uiz --serve --host 127.0.0.1 --port 9000
```

### REST API Endpoints

#### Device Management
- `GET /devices` - List connected devices (Android/iOS)
- `GET /health` - Server health check

#### Test Execution
- `POST /command` - Execute single command
- `POST /testcase` - Execute test case list
- `POST /yaml_testcase` - Execute YAML test configuration
- `GET /session/{session_id}` - Get execution session status

#### WebSocket Connection
- `WS /ws/{session_id}` - Real-time execution feedback

#### Documentation
- `GET /docs` - Swagger UI interactive documentation
- `GET /redoc` - ReDoc alternative documentation

### API Request Examples

#### Execute Single Command
```json
{
  "command": "find and click settings icon",
  "device_id": "optional_device_id",
  "timeout": 30000
}
```

#### Execute Test Cases
```json
{
  "test_cases": [
    "find and click settings",
    "scroll to bottom",
    "click about phone"
  ],
  "device_id": "optional_device_id",
  "include_history": true,
  "debug": false
}
```

#### Execute YAML Test Case
```json
{
  "yaml_config": {
    "android": {"deviceId": "device123"},
    "tasks": [
      {
        "name": "Settings Test",
        "flow": [
          {"ai": "find and click settings"},
          {"sleep": 2000},
          {"aiAssert": "settings page is visible"}
        ]
      }
    ]
  },
  "include_history": true,
  "debug": false
}
```

### WebSocket Messages

#### Connection
- `connected` - Connection established
- `ping/pong` - Heartbeat messages

#### Execution Feedback
- `screenshot` - Base64 encoded screenshot
- `preaction` - Before action execution
- `postaction` - After action execution with remaining iterations
- `stream_response` - AI model streaming response

### Building Web Frontend

The API server enables building web frontends that can:
1. List and select Android devices
2. Execute commands and test cases remotely
3. Receive real-time execution feedback via WebSocket
4. Display screenshots and action progress
5. Show AI model thinking process and responses

### Interactive API Documentation

FastAPI automatically generates interactive documentation:
- **Swagger UI**: Available at `/docs` - Interactive API explorer with request/response examples
- **ReDoc**: Available at `/redoc` - Alternative documentation format

These provide:
- Interactive API testing directly in the browser
- Automatic request/response examples
- Schema validation and type information
- WebSocket connection details

Example WebSocket connection:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/session_123');
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log('Received:', message.type, message.data);
};
```

### Git and Commit Guidelines
- Never mention yourself and claude in any git commit msgs
- Always check that all outputs in @ui_zero/ are localized
- Use @scripts/compile_translations.py to compile *.po files, there is no msgfmt command in this enviroment
