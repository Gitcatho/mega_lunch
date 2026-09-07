# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Preload the following week's menu every Saturday at 9:00 AM KST so the first command can use the prepared cache. Prefetch failures are logged without interrupting the bot. (commit: b83f1fa)

### Fixed (Bug Fixes)

- Detect menu table boundaries so day images remain aligned when the weekly image shifts vertically and exclude the Take-Out section, with configured crop ratios as a fallback. (commit: 78a97c2)

[Unreleased]: https://github.com/Gitcatho/mega_lunch/compare/main...HEAD
