fn main() {
    tauri_build::build();

    // tauri-build embeds the Common Controls v6 manifest into the app binary
    // only. Integration tests that build a mock App (tests/sidecar_command.rs)
    // link comctl32's TaskDialogIndirect, which exists only in v6; without
    // the manifest the test exe dies at load with STATUS_ENTRYPOINT_NOT_FOUND
    // (0xC0000139). `-tests` scopes this to test targets: release binaries are
    // untouched.
    //
    // Cargo rejects `rustc-link-arg-tests` outright ("invalid instruction")
    // when the package has no test target, so emit it only while tests/
    // actually holds one.
    println!("cargo:rerun-if-changed=tests");
    if std::env::var("CARGO_CFG_TARGET_ENV").as_deref() == Ok("msvc") && has_integration_tests() {
        println!("cargo:rustc-link-arg-tests=/MANIFEST:EMBED");
        println!(
            "cargo:rustc-link-arg-tests=/MANIFESTDEPENDENCY:type='win32' \
             name='Microsoft.Windows.Common-Controls' version='6.0.0.0' \
             processorArchitecture='*' publicKeyToken='6595b64144ccf1df' language='*'"
        );
    }
}

/// Mirrors Cargo's test-target auto-discovery: `tests/*.rs` or `tests/*/main.rs`.
fn has_integration_tests() -> bool {
    let Ok(entries) = std::fs::read_dir("tests") else {
        return false;
    };
    entries.flatten().any(|entry| {
        let path = entry.path();
        if path.is_dir() {
            path.join("main.rs").is_file()
        } else {
            path.extension().is_some_and(|ext| ext == "rs")
        }
    })
}
