# Security and data integrity

This application modifies binary NFC dumps. Incorrect offsets or unsupported save layouts can corrupt a dump.

- Keep independent backups of all source dumps.
- Report reproducible crashes or validation failures through GitHub Issues without attaching private dumps.
- Do not treat an internal checksum/readback pass as proof of in-game compatibility.
- Fresh-save initialization is experimental and restricted to mapped Trap Team character IDs.
