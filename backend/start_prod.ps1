# PowerShell 生产环境启动脚本

# 设置错误处理
$ErrorActionPreference = "Stop"

# 检查虚拟环境是否存在
if (-not (Test-Path ".venv")) {
    Write-Host "创建虚拟环境..."
    python -m venv .venv
}

# 激活虚拟环境
Write-Host "激活虚拟环境..."
$ActivationScript = ".venv\Scripts\Activate.ps1"
if (Test-Path $ActivationScript) {
    & $ActivationScript
} else {
    Write-Error "无法找到激活脚本: $ActivationScript"
    exit 1
}

# 安装依赖
Write-Host "安装/更新依赖..."
& python -m pip install --upgrade pip
& python -m pip install -r requirements.txt

# 检查 .env 文件
if (-not (Test-Path ".env")) {
    Write-Host "复制 .env.example 到 .env"
    Copy-Item ".env.example" ".env"
    Write-Host "请编辑 .env 文件以配置环境变量"
}

# 创建上传目录
if (-not (Test-Path "uploads")) {
    New-Item -ItemType Directory -Path "uploads"
    Write-Host "创建 uploads 目录"
}

# 启动应用
Write-Host "启动生产服务器..."
$env:PYTHONPATH = $(Get-Location)
& gunicorn app.main:app -c gunicorn_conf.py