# Changelog

## 0.1.0 (2026-09-08)


### Features

* **cli:** distinct exit codes so callers can tell the failure modes apart ([309d816](https://github.com/nicolasgalvez/stream-tools/commit/309d816915c34af87a72d13b7a18fe0f968f864a))
* **playlists:** PlaylistService for listing and membership ([3d4e50e](https://github.com/nicolasgalvez/stream-tools/commit/3d4e50ec247a8fb5bd326bf6eeb636508ffd5f11))
* **scripts:** add cron-safe batch YouTube uploader ([#12](https://github.com/nicolasgalvez/stream-tools/issues/12)) ([2b15cf8](https://github.com/nicolasgalvez/stream-tools/commit/2b15cf8c82d8c97d669e6451ba555a03a246947c))
* **videos:** typed errors for quota and committed-but-unconfirmed uploads ([44172d2](https://github.com/nicolasgalvez/stream-tools/commit/44172d26d990dfb255d9fe5d9b5012b589678b78))


### Bug Fixes

* **cli:** stop Rich decorating the machine-readable video_id line ([3f35e5e](https://github.com/nicolasgalvez/stream-tools/commit/3f35e5e1059209c1c61fd438f307be74671879fa))
* **VGM-40:** stop passing `mine` to videos.list ([#30](https://github.com/nicolasgalvez/stream-tools/issues/30)) ([442e29f](https://github.com/nicolasgalvez/stream-tools/commit/442e29fcf39e922af0c5d79f83b4d811feee6d64))
* **VGM-78:** refuse a publish time on a video that is not private ([#32](https://github.com/nicolasgalvez/stream-tools/issues/32)) ([1adb1fc](https://github.com/nicolasgalvez/stream-tools/commit/1adb1fc2d2f5db6469be31f09893259ba08af59a))


### Documentation

* add MCP server instructions to README ([#27](https://github.com/nicolasgalvez/stream-tools/issues/27)) ([6b116cd](https://github.com/nicolasgalvez/stream-tools/commit/6b116cd4123ed030d4f1d77ff631b54c65ff455f))
