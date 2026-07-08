# Changelog

All notable changes to this project will be documented in this file.

## [1.1.0] - 2024-07-08

### Changed
- **Dependency Updates:**
  - Updated `zenoh-python>=0.11.0` to `eclipse-zenoh>=1.9.0` in all dependency files
  - Updated `apache-iotdb>=1.0.0` to `apache-iotdb>=2.0.0` in all dependency files
  - Files updated: `requirements.txt`, `panel/requirements.txt`, `pyproject.toml`

- **API Migration:**
  - Updated `src/zenoh_client.py` to use the new eclipse-zenoh API (1.9.0+)
    - Replaced `Zenoh` class with `zenoh.open()` and `zenoh.Config()`
    - Replaced `Workspace` with `session.workspace()`
    - Updated `get()` method to handle new Reply/Sample API
    - Updated `subscribe()` method to use `declare_subscriber()`
  - Updated `Parts/part_final.py` to use the new eclipse-zenoh API
    - Replaced `Zenoh` class with `zenoh.open()` and `zenoh.Config()`
    - Updated sample processing to handle new Sample API

- **CI/CD Updates:**
  - Updated `.github/workflows/test.yml` to install `eclipse-zenoh>=1.9.0` and `apache-iotdb>=2.0.0`
  - Updated `.github/workflows/pylint.yml` to install correct packages
  - Updated `.github/workflows/lint.yml` to install correct packages and use newer action versions

- **Test Updates:**
  - Updated `tests/test_zenoh_client.py` to mock the new eclipse-zenoh API
  - Updated mocks to match new `zenoh.open()`, `Config`, `Session`, and `Sample` objects

- **Documentation Updates:**
  - Updated `README.md` to reference `eclipse-zenoh` instead of `Zenoh`
  - Updated installation instructions to use correct package names
  - Updated `UsefulLinks.md` to point to eclipse-zenoh documentation

### Fixed
- Fixed dependency resolution errors in CI pipeline
- Fixed import errors due to old zenoh-python package name
- Fixed API compatibility issues with eclipse-zenoh 1.9.0+

### Notes
- The following files were already using the new API and required no changes:
  - `panel/panel_app.py`
  - `zenoh_producer.py`
  - `zenoh_retrieve.py`
  - `zenoh_subscriber.py`
- Backward compatibility with older zenoh versions is not maintained in this update
