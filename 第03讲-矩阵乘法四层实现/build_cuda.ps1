# build_cuda.ps1 —— 第03讲 CUDA 层可复现构建/运行脚本（真机实测通过）
# 用法：pwsh -File code\build_cuda.ps1            # 编译 + 运行全部
#       pwsh -File code\build_cuda.ps1 -BuildOnly # 只编译
param([switch]$BuildOnly)

$ErrorActionPreference = "Stop"

# ---- 路径（本机实际位置）----
$TK  = "D:\DeepSeek-Harness\hw-0304\tools\cuda13\nvidia\cu13"
$VC  = "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
$LAB = Split-Path -Parent $PSScriptRoot
$BUILD = Join-Path $LAB "build"
$LOGS  = Join-Path $LAB "logs"

if (-not (Test-Path "$TK\bin\nvcc.exe"))   { throw "找不到 nvcc: $TK\bin\nvcc.exe" }
if (-not (Test-Path $VC))                  { throw "找不到 vcvars64.bat: $VC" }
New-Item -ItemType Directory -Force -Path $BUILD,$LOGS | Out-Null

function Invoke-Nvcc {
    param([string]$Defs, [string]$Src, [string]$Exe)
    # nvcc 需要 cl.exe 当 host 编译器 -> 必须包在 vcvars64 里
    $cmd = "call `"$VC`" >nul 2>&1 && cd /d `"$LAB`" && " +
           "`"$TK\bin\nvcc.exe`" -O2 -arch=sm_89 -Xcompiler /utf-8 $Defs " +
           "-I`"$TK\include`" `"$Src`" -o `"build\$Exe`" -L`"$TK\lib\x64`" -lcudart"
    Write-Host "== nvcc $Src -> build\$Exe" -ForegroundColor Cyan
    cmd /c $cmd
    if ($LASTEXITCODE -ne 0) { throw "nvcc 编译失败: $Src (exit=$LASTEXITCODE)" }
    Write-Host "   OK (exit=0)"
}

function Invoke-Run {
    param([string]$Exe, [string]$LogName)
    # 运行期需要 cudart64_13.dll -> 把 bin\x86_64 放进 PATH
    $env:PATH = "$TK\bin\x86_64;$TK\bin;$env:PATH"
    Write-Host "== run build\$Exe" -ForegroundColor Cyan
    $out = & (Join-Path $BUILD $Exe) 2>&1
    $out | ForEach-Object { $_ }
    $out | Out-File -Encoding utf8 (Join-Path $LOGS $LogName)
}

# ---- 1. 教学版：3x3，一线程一元素，blockDim=32x32 ----
Invoke-Nvcc -Defs "" -Src "code\matmul.cu" -Exe "matmul_cu.exe"
# ---- 2. 基准版：N=1024 CPU vs GPU naive vs GPU tiled ----
Invoke-Nvcc -Defs "-DN=1024" -Src "code\matmul_cu_bench.cu" -Exe "matmul_cu_bench.exe"

if ($BuildOnly) { Write-Host "`n构建完成（-BuildOnly，未运行）。"; return }

Invoke-Run -Exe "matmul_cu.exe" -LogName "run_cuda.txt"
Invoke-Run -Exe "matmul_cu_bench.exe" -LogName "cuda_bench.txt"
Write-Host "`n全部完成：日志见 logs\run_cuda.txt 与 logs\cuda_bench.txt" -ForegroundColor Green