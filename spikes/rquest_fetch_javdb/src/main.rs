//! JavDB fetch spike — `rquest` (browser TLS fingerprint emulation)
//!
//! 用 `rquest` + `rquest-util` 的 Chrome emulation 取代純 `reqwest`，
//! 驗證能否繞過 Cloudflare TLS 指紋偵測。
//!
//! 用法：
//!     cargo run -- "https://javdb.com/v/xxxx"
//!
//! 不會輸出 cookie 或完整 magnet 連結。

use std::env;
use std::fs;
use std::path::PathBuf;
use std::process::ExitCode;

use scraper::{Html, Selector};
use serde::Serialize;

use rquest::Client;
use rquest_util::Emulation;

#[derive(Serialize)]
struct Summary {
    ok: bool,
    http_status: u16,
    engine: &'static str,
    emulation: &'static str,
    title: String,
    code: String,
    magnet_count: usize,
    first_magnet_starts_with_magnet: bool,
    challenge_suspected: bool,
    error: Option<String>,
}

impl Summary {
    fn fail(http_status: u16, msg: impl Into<String>, emulation: &'static str) -> Self {
        Self {
            ok: false,
            http_status,
            engine: "rquest",
            emulation,
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

/// 找到 repo root 下的 cookies.txt 並回傳原始字串
fn read_cookies() -> Result<String, String> {
    let mut candidates: Vec<PathBuf> = Vec::new();

    if let Ok(manifest_dir) = env::var("CARGO_MANIFEST_DIR") {
        let mut p = PathBuf::from(manifest_dir);
        p.pop();
        p.pop();
        p.push("cookies.txt");
        candidates.push(p);
    }

    if let Ok(cwd) = env::current_dir() {
        let mut p = cwd.clone();
        for _ in 0..5 {
            candidates.push(p.join("cookies.txt"));
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

    Err(format!("找不到 cookies.txt（嘗試 {} 個位置）", candidates.len()))
}

/// 模仿 Python `parent.get_text(strip=True)`
fn extract_code(doc: &Html) -> String {
    let panel_a = Selector::parse(".panel-block .value a").unwrap();
    if let Some(a) = doc.select(&panel_a).next() {
        if let Some(parent) = a.parent() {
            if let Some(elem) = scraper::ElementRef::wrap(parent) {
                return elem
                    .text()
                    .map(str::trim)
                    .filter(|s| !s.is_empty())
                    .collect::<Vec<_>>()
                    .join("");
            }
        }
        return a.text().collect::<String>().trim().to_string();
    }
    String::new()
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

async fn run(url: &str) -> Summary {
    const EMULATION_NAME: &str = "Chrome131";

    let cookie = match read_cookies() {
        Ok(c) => c,
        Err(e) => return Summary::fail(0, e, EMULATION_NAME),
    };
    if cookie.is_empty() {
        return Summary::fail(0, "cookies.txt 是空的", EMULATION_NAME);
    }

    let client = match Client::builder().emulation(Emulation::Chrome131).build() {
        Ok(c) => c,
        Err(e) => {
            return Summary::fail(0, format!("建立 rquest client 失敗: {}", e), EMULATION_NAME)
        }
    };

    // 沿用與 Python create_session 一致的 headers（除了 User-Agent，emulation 會自帶）
    let resp = match client
        .get(url)
        .header(
            "Accept",
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        )
        .header(
            "Accept-Language",
            "zh-TW,zh;q=0.9,ja;q=0.8,en-US;q=0.7,en;q=0.6",
        )
        .header("Accept-Encoding", "gzip, deflate, br")
        .header("Connection", "keep-alive")
        .header("Upgrade-Insecure-Requests", "1")
        .header("Sec-Fetch-Dest", "document")
        .header("Sec-Fetch-Mode", "navigate")
        .header("Sec-Fetch-Site", "none")
        .header("Sec-Fetch-User", "?1")
        .header("Cache-Control", "max-age=0")
        .header("cookie", &cookie)
        .send()
        .await
    {
        Ok(r) => r,
        Err(e) => return Summary::fail(0, format!("HTTP 請求失敗: {}", e), EMULATION_NAME),
    };

    let http_status = resp.status().as_u16();

    let body = match resp.text().await {
        Ok(t) => t,
        Err(e) => {
            return Summary::fail(http_status, format!("讀取 body 失敗: {}", e), EMULATION_NAME)
        }
    };

    if http_status != 200 {
        return Summary {
            ok: false,
            http_status,
            engine: "rquest",
            emulation: EMULATION_NAME,
            title: String::new(),
            code: String::new(),
            magnet_count: 0,
            first_magnet_starts_with_magnet: false,
            challenge_suspected: detect_challenge(&body, false),
            error: Some(format!("HTTP {}", http_status)),
        };
    }

    let doc = Html::parse_document(&body);

    let title_sel = Selector::parse("h2.title.is-4 .current-title").unwrap();
    let title = doc
        .select(&title_sel)
        .next()
        .map(|n| n.text().collect::<String>().trim().to_string())
        .unwrap_or_default();

    let code = extract_code(&doc);

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

    let has_container =
        doc.select(&Selector::parse("#magnets-content").unwrap()).next().is_some();
    let challenge_suspected = detect_challenge(&body, has_container);

    Summary {
        ok: magnets_count > 0,
        http_status,
        engine: "rquest",
        emulation: EMULATION_NAME,
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
    eprintln!("使用 rquest + Chrome131 emulation 嘗試繞過 Cloudflare TLS 指紋偵測。");
}

#[tokio::main(flavor = "current_thread")]
async fn main() -> ExitCode {
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

    let summary = run(url).await;
    summary.print();
    if summary.ok {
        ExitCode::SUCCESS
    } else {
        ExitCode::from(1)
    }
}
