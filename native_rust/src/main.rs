// native_rust/src/main.rs — SON v3 Native Security Core Runtime
mod security_core;

use std::env;
use security_core::NativePathGuard;

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() > 2 && args[1] == "--check-path" {
        let guard = NativePathGuard::new();
        match guard.is_path_safe(&args[2]) {
            Ok(safe) => println!("SAFE: {}", safe.display()),
            Err(e) => {
                eprintln!("BLOCKED: {}", e);
                std::process::exit(1);
            }
        }
        return;
    }

    println!("SON V3 - Native Rust Security Core Online.");
    println!("Status: Modular accelerator ready. Running in zero-trust defensive mode.");
}
