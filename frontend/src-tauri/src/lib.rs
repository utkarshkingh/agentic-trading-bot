// On desktop the Python backend ships as a sidecar binary that we spawn on
// startup and terminate when the window closes. On mobile there is no sidecar
// (the app talks to a backend over the network), so this is desktop-only.

#[cfg(desktop)]
use std::sync::Mutex;
#[cfg(desktop)]
use tauri::Manager;
#[cfg(desktop)]
use tauri_plugin_shell::{process::CommandChild, ShellExt};

#[cfg(desktop)]
struct BackendProcess(Mutex<Option<CommandChild>>);

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let builder = tauri::Builder::default().plugin(tauri_plugin_shell::init());

    #[cfg(desktop)]
    let builder = builder
        .setup(|app| {
            let sidecar = app
                .shell()
                .sidecar("trading-backend")
                .expect("failed to create backend sidecar command");
            let (_rx, child) = sidecar.spawn().expect("failed to spawn backend sidecar");
            app.manage(BackendProcess(Mutex::new(Some(child))));
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                if let Some(state) = window.app_handle().try_state::<BackendProcess>() {
                    if let Some(child) = state.0.lock().unwrap().take() {
                        let _ = child.kill();
                    }
                }
            }
        });

    builder
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
