# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.6]

### Added
- **AI Assertion Support**: Implement AI-powered assertions in YAML test configurations
  - Added `aiAssert` action type for dynamic UI state validation
  - Smart assertion logic: AI model evaluates conditions and returns true/false based on current screen content
  - Configurable error handling: Support `continueOnError` flag to control execution flow on assertion failures
  - Single-iteration assertion evaluation (`max_iters=1`) for efficient testing
  - Exception-based flow control: RuntimeError on assertion failure when `continueOnError=false`

### Enhanced
- **YAML Configuration Support**: Extended YAML test configuration with assertion capabilities
  ```yaml
  tasks:
    - name: "Validation Task"
      continueOnError: false
      flow:
        - aiAssert: "Settings page is visible"
        - aiAssert: "WiFi toggle is enabled"
  ```

### Internationalization
- Added 9 new localization keys for assertion actions
- Compiled translation files for both Chinese (zh_CN) and English (en_US)
- Consistent messaging across CLI and GUI modes

### Testing
- Fixed test expectations to properly validate `ai_assert` action type
- Updated integration tests for full YAML processing pipeline
- All 52 tests passing with new assertion functionality

### UI/UX Improvements
- Clear assertion status indicators: ✅ for pass, ❌ for fail
- Detailed task progress reporting with assertion results
- Improved user experience with contextual error messages

### Technical Changes
- Enhanced `execute_unified_action()` function with `ai_assert` action type handling
- AI model responds with `Action: finished(content='Assert is true/false')` format
- Updated CLI output with localized assertion messaging

## [0.1.5] - Previous Release
- Version bump and maintenance updates
- Enhanced localization support for execute_wait_action tests
- Refactored TestRunner to StepRunner and enhanced localization in tests
- Added integration tests for CLI module and enhanced YAML processing