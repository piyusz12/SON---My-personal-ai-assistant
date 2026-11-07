// native_rust/src/security_core.rs — High-Performance Native Security Utilities for SON v3
// Modular Rust component for high-throughput audit hashing and native path verification.

use std::path::{Path, PathBuf};

pub struct NativePathGuard {
    forbidden_prefixes: Vec<&'static str>,
}

impl NativePathGuard {
    pub fn new() -> Self {
        Self {
            forbidden_prefixes: vec![
                "c:\\windows",
                "c:\\program files",
                "/etc",
                "/usr",
                "/var",
            ],
        }
    }

    pub fn is_path_safe(&self, raw_path: &str) -> Result<PathBuf, String> {
        if raw_path.trim().is_empty() {
            return Err("Empty path provided".to_string());
        }

        if raw_path.contains('\0') {
            return Err("Null byte detected in path".to_string());
        }

        let p = Path::new(raw_path);
        let canonical = match p.canonicalize() {
            Ok(c) => c,
            Err(_) => p.to_path_buf(),
        };

        let path_str = canonical.to_string_lossy().to_lowercase();
        for forbidden in &self.forbidden_prefixes {
            if path_str.starts_with(forbidden) {
                return Err(format!("Access to protected system path '{}' is forbidden", path_str));
            }
        }

        // Check for sensitive credential markers
        let sensitive_markers = [".env", "id_rsa", ".ssh", ".aws", "credentials"];
        for marker in &sensitive_markers {
            if path_str.contains(marker) {
                return Err(format!("Access to credential store containing '{}' is forbidden", marker));
            }
        }

        Ok(canonical)
    }
}

