// dot.rs —— Scaled Dot-Product 的 Rust 实现（仅标准库）
//
// 统一接口：fn dot(a: &[f64], b: &[f64]) -> f64
// 读数：读 gen_data.py 生成的裸 float64 小端二进制文件（无文件头）。
//
// 编译（务必 --release，即 -C opt-level=3）：
//     set PATH=<工具链>\bin;%PATH%
//     rustc --edition 2021 -C opt-level=3 -o build\dot_rs.exe code\dot.rs
//   （本机 rustc 是 stable-x86_64-pc-windows-gnu，链接时用 mingw 的 gcc/ld）
//
// 用法：
//     dot_rs.exe a_10000_f64.bin b_10000_f64.bin            # 一次性求值
//     dot_rs.exe --serve a_10000_f64.bin b_10000_f64.bin    # 应答式 worker
//
// 应答协议与 dot.py --serve / dot_c.exe --serve 完全一致：READY n；b / r <k> / q。
//
// 防优化：结果累加进 total 并打印（std::hint::black_box 再兜一层）；
// dot 标 inline(never)，防止 k 次重复被折叠成 1 次。

use std::env;
use std::fs::File;
use std::io::{self, BufRead, Read, Write};
use std::process;
use std::hint::black_box;

#[inline(never)]
fn dot(a: &[f64], b: &[f64]) -> f64 {
    debug_assert_eq!(a.len(), b.len());
    let mut s = 0.0f64;
    let n = a.len();
    for i in 0..n {
        s += a[i] * b[i];   // 顺序累加，与 Python / C 版一致
    }
    s
}

// 读裸 float64 小端文件；返回 Vec<f64>
fn load_f64(path: &str) -> Result<Vec<f64>, String> {
    let mut f = File::open(path).map_err(|e| format!("cannot open {}: {}", path, e))?;
    let mut buf = Vec::new();
    f.read_to_end(&mut buf).map_err(|e| format!("read {}: {}", path, e))?;
    if buf.len() % 8 != 0 {
        return Err(format!("bad size {} for {} (not a multiple of 8)", buf.len(), path));
    }
    // 显式按小端解释，杜绝「读错字节序」类错误
    let out: Vec<f64> = buf
        .chunks_exact(8)
        .map(|c| {
            let arr: [u8; 8] = c.try_into().unwrap();
            f64::from_le_bytes(arr)
        })
        .collect();
    Ok(out)
}

fn run_once(pa: &str, pb: &str) -> Result<(), String> {
    let a = load_f64(pa)?;
    let b = load_f64(pb)?;
    if a.len() != b.len() {
        return Err(format!("dimension mismatch: {} vs {}", a.len(), b.len()));
    }
    let s = dot(&a, &b);
    println!("N={} SUM={:.17e}", a.len(), s);
    Ok(())
}

fn run_serve(pa: &str, pb: &str) -> Result<(), String> {
    let a = load_f64(pa)?;
    let b = load_f64(pb)?;
    if a.len() != b.len() {
        return Err(format!("dimension mismatch: {} vs {}", a.len(), b.len()));
    }
    let stdout = io::stdout();
    let mut out = stdout.lock();
    writeln!(out, "READY {}", a.len()).map_err(|e| e.to_string())?;
    out.flush().map_err(|e| e.to_string())?;

    let stdin = io::stdin();
    for line in stdin.lock().lines() {
        let line = line.map_err(|e| e.to_string())?;
        let cmd = line.trim();
        if cmd.is_empty() {
            continue;
        }
        match cmd.as_bytes()[0] {
            b'q' => break,
            b'b' => {
                writeln!(out, "0").map_err(|e| e.to_string())?;
                out.flush().map_err(|e| e.to_string())?;
            }
            b'r' => {
                let k: i64 = cmd[1..].trim().parse().unwrap_or(0);
                let k = if k < 0 { 0 } else { k };
                let mut total = 0.0f64;
                for _ in 0..k {
                    total += dot(black_box(&a), black_box(&b));
                }
                writeln!(out, "{:.17e}", total).map_err(|e| e.to_string())?;
                out.flush().map_err(|e| e.to_string())?;
            }
            _ => {
                writeln!(out, "ERR unknown command").map_err(|e| e.to_string())?;
                out.flush().map_err(|e| e.to_string())?;
                break;
            }
        }
    }
    Ok(())
}

fn main() {
    let args: Vec<String> = env::args().collect();
    let r = if args.len() >= 4 && args[1] == "--serve" {
        run_serve(&args[2], &args[3])
    } else if args.len() >= 3 {
        run_once(&args[1], &args[2])
    } else {
        eprintln!("usage: dot_rs [--serve] <a.bin> <b.bin>");
        process::exit(2);
    };
    if let Err(e) = r {
        eprintln!("ERR {}", e);
        process::exit(1);
    }
}
