// 这是 Tauri 桌面壳的入口（Rust）。当前机器未装 Rust，无法编译——这是骨架与示例。
// 功能：启动时拉起 Python 核心(后台 serve)，退出时关闭它；窗口里加载 frontend/dist。
// TODO(装 Rust 后)：`npm i -g @tauri-apps/cli` -> `npm --prefix ../frontend run build` -> `cargo tauri build`
fn main() {
    // 1) 拉起 Python 后端（python main.py serve -> 127.0.0.1:8090）
    let _backend = std::process::Command::new("python")
        .args(["-c", "import sys;sys.path.insert(0,'.');from core.pipeline import *;exec(open('main.py').read())"])
        .current_dir("..")
        .spawn()
        .ok();

    // 2) 启动 Tauri 窗口，加载 frontend/dist（内含签发台 UI）
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .run(tauri::generate_context!())
        .expect("error while running haibala desktop app");
}
