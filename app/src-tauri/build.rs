mod build_support;

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
    // actually holds one. The detection lives in build_support.rs, which the
    // lib unit tests also compile and test.
    println!("cargo:rerun-if-changed=tests");
    println!("cargo:rerun-if-changed=build_support.rs");
    if std::env::var("CARGO_CFG_TARGET_ENV").as_deref() == Ok("msvc")
        && build_support::has_integration_tests(std::path::Path::new("tests"))
    {
        println!("cargo:rustc-link-arg-tests=/MANIFEST:EMBED");
        println!(
            "cargo:rustc-link-arg-tests=/MANIFESTDEPENDENCY:type='win32' \
             name='Microsoft.Windows.Common-Controls' version='6.0.0.0' \
             processorArchitecture='*' publicKeyToken='6595b64144ccf1df' language='*'"
        );
    }
}
