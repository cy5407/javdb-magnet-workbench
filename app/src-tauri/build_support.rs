//! Logic used by build.rs, kept in its own file so the lib unit tests can
//! compile it too (lib.rs includes it under `cfg(test)`): a build script has
//! no test harness of its own.

use std::path::Path;

/// Mirrors Cargo's test-target auto-discovery: `tests/*.rs` or `tests/*/main.rs`.
/// A build script cannot see the resolved target list, so this assumes the
/// manifest keeps auto-discovery (no `autotests = false`, no `[[test]]` with a
/// path outside tests/). Change either and this check must change with it.
pub fn has_integration_tests(tests_dir: &Path) -> bool {
    let Ok(entries) = std::fs::read_dir(tests_dir) else {
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

#[cfg(test)]
mod tests {
    use super::has_integration_tests;
    use std::fs;
    use std::path::PathBuf;
    use std::sync::atomic::{AtomicU32, Ordering};

    /// A fresh directory under the system temp dir. Cleanup deletes the
    /// files each test created one by one, then the empty directories.
    struct Scratch {
        root: PathBuf,
        files: Vec<PathBuf>,
        dirs: Vec<PathBuf>,
    }

    impl Scratch {
        fn new() -> Self {
            static N: AtomicU32 = AtomicU32::new(0);
            let root = std::env::temp_dir().join(format!(
                "jmw-build-support-{}-{}",
                std::process::id(),
                N.fetch_add(1, Ordering::Relaxed)
            ));
            fs::create_dir(&root).expect("create scratch dir");
            Self { root, files: Vec::new(), dirs: Vec::new() }
        }

        fn file(&mut self, rel: &str) {
            let path = self.root.join(rel);
            if let Some(parent) = path.parent() {
                if parent != self.root && !parent.exists() {
                    fs::create_dir(parent).expect("create sub dir");
                    self.dirs.push(parent.to_path_buf());
                }
            }
            fs::write(&path, "").expect("write file");
            self.files.push(path);
        }

        fn dir(&mut self, rel: &str) {
            let path = self.root.join(rel);
            fs::create_dir(&path).expect("create dir");
            self.dirs.push(path);
        }
    }

    impl Drop for Scratch {
        fn drop(&mut self) {
            for f in &self.files {
                let _ = fs::remove_file(f);
            }
            for d in self.dirs.iter().rev() {
                let _ = fs::remove_dir(d);
            }
            let _ = fs::remove_dir(&self.root);
        }
    }

    #[test]
    fn missing_tests_dir_has_no_integration_tests() {
        let s = Scratch::new();
        assert!(!has_integration_tests(&s.root.join("tests")));
    }

    #[test]
    fn empty_tests_dir_has_no_integration_tests() {
        let s = Scratch::new();
        assert!(!has_integration_tests(&s.root));
    }

    #[test]
    fn non_rust_files_are_not_test_targets() {
        let mut s = Scratch::new();
        s.file("README.md");
        s.file("fixture.json");
        assert!(!has_integration_tests(&s.root));
    }

    #[test]
    fn top_level_rs_file_is_a_test_target() {
        let mut s = Scratch::new();
        s.file("sidecar_command.rs");
        assert!(has_integration_tests(&s.root));
    }

    #[test]
    fn subdir_needs_main_rs_to_be_a_test_target() {
        let mut s = Scratch::new();
        s.dir("helpers");
        s.file("helpers/util.rs");
        assert!(!has_integration_tests(&s.root), "subdir without main.rs");

        let mut s = Scratch::new();
        s.file("suite/main.rs");
        assert!(has_integration_tests(&s.root), "subdir with main.rs");
    }
}
