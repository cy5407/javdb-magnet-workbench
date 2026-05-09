//! JavDB fetch spike (Rust)
//!
//! 驗證能否用純 `reqwest`（rustls）+ `scraper` 抓 JavDB 影片頁並解析磁力連結。
//! 結論將決定 Rust/Tauri 重寫是否需要 curl-impersonate 或 Python sidecar。
//!
//! 用法：
//!     cargo run -- "https://javdb.com/v/xxxx"
//!
//! 輸出：JSON summary。不會輸出 cookie 值或完整 magnet 連結。

use std::env;
use std::fs;
use std::path::PathBuf;
use std::process::ExitCode;

use scraper::{Html, Selector};
use serde::Serialize;

#[derive(Serialize)]
struct Summary {
    ok: bool,
    http_status: u16,
    engine: &'static str,
    title: String,
    code: String,
    magnet_count: usize,
    first_magnet_starts_with_magnet: bool,
    challenge_suspected: bool,
    error: Option<String>,
}

impl Summary {
    fn fail(http_status: u16, msg: impl Into<String>) -> Self {
        Self {
            ok: false,
            http_status,
            engine: "reqwest",
            title: String::new(),
            code: String::new(),
            magnet_count: 0,
            first_magnet_starts_with_magnet: false,
            challenge_suspected: false,
            error: Some(msg.into()),
        }
    }

    fn print(&self) {
        match serde_json::to_string_pretty(self) {
            Ok(s) => println!("{}", s),
            Err(e) => eprintln!("無法序列化 summary: {}", e),
        }
    }
}

/// 找到 repo root 下的 cookies.txt 並回傳原始字串。
/// 嘗試以下順序：
///   1) CARGO_MANIFEST_DIR/../../cookies.txt（cargo run 時）
///   2) 從目前 working directory 往上找（最多 5 層）
///   3) 從 current_exe() 所在路徑往上找（最多 6 層，含 target/release）
fn read_cookies() -> Result<String, String> {
    let mut candidates: Vec<PathBuf> = Vec::new();

    if let Ok(manifest_dir) = env::var("CARGO_MANIFEST_DIR") {
        let mut p = PathBuf::from(manifest_dir);
        p.pop(); // spikes/
        p.pop(); // repo root
        p.push("cookies.txt");
        candidates.push(p);
    }

    if let Ok(cwd) = env::current_dir() {
        let mut p = cwd.clone();
        for _ in 0..5 {
            let try_p = p.join("cookies.txt");
            candidates.push(try_p);
            if !p.pop() {
                break;
            }
        }
    }

    if let Ok(exe) = env::current_exe() {
        let mut p = exe;
        for _ in 0..6 {
            if !p.pop() {
                break;
            }
            candidates.push(p.join("cookies.txt"));
        }
    }

    for cand in &candidates {
        if cand.exists() {
            return fs::read_to_string(cand)
                .map(|s| s.trim().to_string())
                .map_err(|e| format!("讀取 cookies.txt 失敗: {}", e));
        }
    }

    Err(format!(
        "找不到 cookies.txt（嘗試 {} 個位置）",
        candidates.len()
    ))
}

fn build_client(cookie: &str) -> Result<reqwest::blocking::Client, reqwest::Error> {
    use reqwest::header::{HeaderMap, HeaderName, HeaderValue};

    let mut headers = HeaderMap::new();
    let pairs: &[(&str, &str)] = &[
        (
            "Accept",
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        ),
        ("Accept-Language", "zh-TW,zh;q=0.9,ja;q=0.8,en-US;q=0.7,en;q=0.6"),
        ("Accept-Encoding", "gzip, deflate, br"),
        ("Connection", "keep-alive"),
        ("Upgrade-Insecure-Requests", "1"),
        ("Sec-Fetch-Dest", "document"),
        ("Sec-Fetch-Mode", "navigate"),
        ("Sec-Fetch-Site", "none"),
        ("Sec-Fetch-User", "?1"),
        ("Cache-Control", "max-age=0"),
        (
            "User-Agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 \
             (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        ),
    ];
    for (k, v) in pairs {
        if let (Ok(name), Ok(value)) = (HeaderName::from_bytes(k.as_bytes()), HeaderValue::from_str(v)) {
            headers.insert(name, value);
        }
    }
    if let Ok(value) = HeaderValue::from_str(cookie) {
        headers.insert(reqwest::header::COOKIE, value);
    }

    reqwest::blocking::Client::builder()
        .default_headers(headers)
        .timeout(std::time::Duration::from_secs(30))
        .build()
}

/// 嘗試從 panel-block 抽出番號文字（模仿 Python `parent.get_text(strip=True)`）。
fn extract_code(doc: &Html) -> String {
    // .panel-block .value a 第一個（番號）
    let panel_a = Selector::parse(".panel-block .value a").unwrap();
    if let Some(a) = doc.select(&panel_a).next() {
        // 取 a 的父節點（panel-block）所有文字，模擬 Python parent.get_text(strip=True)
        if let Some(parent) = a.parent() {
            // 收集 parent 子樹所有文字
            let text = collect_text(scraper::ElementRef::wrap(parent));
            return text;
        }
        return a.text().collect::<String>().trim().to_string();
    }
    String::new()
}

/// 收集元素所有文字節點，去除多餘空白
fn collect_text(node: Option<scraper::ElementRef>) -> String {
    if let Some(elem) = node {
        elem.text()
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .collect::<Vec<_>>()
            .join("")
    } else {
        String::new()
    }
}

fn detect_challenge(html: &str, has_magnets_container: bool) -> bool {
    if has_magnets_container {
        return false;
    }
    let lower = html.to_lowercase();
    lower.contains("just a moment")
        || lower.contains("cf_clearance")
        || lower.contains("challenge")
}

fn run(url: &str) -> Summary {
    let cookie = match read_cookies() {
        Ok(c) => c,
        Err(e) => return Summary::fail(0, e),
    };
    if cookie.is_empty() {
        return Summary::fail(0, "cookies.txt 是空的");
    }

    let client = match build_client(&cookie) {
        Ok(c) => c,
        Err(e) => return Summary::fail(0, format!("建立 reqwest client 失敗: {}", e)),
    };

    let resp = match client.get(url).send() {
        Ok(r) => r,
        Err(e) => return Summary::fail(0, format!("HTTP 請求失敗: {}", e)),
    };
    let http_status = resp.status().as_u16();

    let body = match resp.text() {
        Ok(t) => t,
        Err(e) => return Summary::fail(http_status, format!("讀取 body 失敗: {}", e)),
    };

    if http_status != 200 {
        return Summary {
            ok: false,
            http_status,
            engine: "reqwest",
            title: String::new(),
            code: String::new(),
            magnet_count: 0,
            first_magnet_starts_with_magnet: false,
            challenge_suspected: detect_challenge(&body, false),
            error: Some(format!("HTTP {}", http_status)),
        };
    }

    let doc = Html::parse_document(&body);

    // title
    let title_sel = Selector::parse("h2.title.is-4 .current-title").unwrap();
    let title = doc
        .select(&title_sel)
        .next()
        .map(|n| n.text().collect::<String>().trim().to_string())
        .unwrap_or_default();

    // code
    let code = extract_code(&doc);

    // magnets
    let magnets_sel = Selector::parse("#magnets-content .item").unwrap();
    let magnet_link_sel = Selector::parse(".magnet-name a").unwrap();
    let mut magnets_count = 0usize;
    let mut first_starts_with_magnet = false;

    for (idx, item) in doc.select(&magnets_sel).enumerate() {
        if let Some(a) = item.select(&magnet_link_sel).next() {
            if let Some(href) = a.value().attr("href") {
                magnets_count += 1;
                if idx == 0 {
                    first_starts_with_magnet = href.starts_with("magnet:");
                }
            }
        }
    }

    // 判定 challenge
    let has_container =
        doc.select(&Selector::parse("#magnets-content").unwrap()).next().is_some();
    let challenge_suspected = detect_challenge(&body, has_container);

    Summary {
        ok: magnets_count > 0,
        http_status,
        engine: "reqwest",
        title,
        code,
        magnet_count: magnets_count,
        first_magnet_starts_with_magnet: first_starts_with_magnet,
        challenge_suspected,
        error: None,
    }
}

fn print_usage() {
    eprintln!("用法: cargo run -- \"https://javdb.com/v/xxxx\"");
    eprintln!();
    eprintln!("從 repo root 的 cookies.txt 讀取 cookie，向指定 URL 發送請求，");
    eprintln!("解析磁力連結並輸出 JSON summary。不會印出 cookie 或完整 magnet。");
}

fn main() -> ExitCode {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        print_usage();
        return ExitCode::from(2);
    }
    let url = &args[1];
    if !url.starts_with("http") {
        eprintln!("URL 必須以 http(s) 開頭");
        print_usage();
        return ExitCode::from(2);
    }

    let summary = run(url);
    summary.print();
    if summary.ok {
        ExitCode::SUCCESS
    } else {
        ExitCode::from(1)
    }
}
