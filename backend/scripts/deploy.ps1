# PowerShell 部署脚本
# 用于在 Windows 环境中部署 FastAPI 应用

# 设置错误处理
$ErrorActionPreference = "Stop"

# 获取脚本目录和应用目录
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$AppDir = Join-Path $ScriptDir ".."
$VenvDir = Join-Path $AppDir ".venv"

# 切换到应用目录
Set-Location $AppDir

Write-Host "创建虚拟环境..."
& python -m venv $VenvDir

# 激活虚拟环境
$ActivationScript = Join-Path $VenvDir "Scripts\Activate.ps1"
if (Test-Path $ActivationScript) {
    & $ActivationScript
} else {
    Write-Error "无法找到激活脚本: $ActivationScript"
    exit 1
}

Write-Host "升级 pip..."
& python -m pip install --upgrade pip

Write-Host "安装依赖..."
& python -m pip install -r requirements.txt

# 检查 .env 文件是否存在，如果不存在则复制示例文件
$EnvFile = Join-Path $AppDir ".env"
if (-not (Test-Path $EnvFile)) {
    $EnvExampleFile = Join-Path $AppDir ".env.example"
    if (Test-Path $EnvExampleFile) {
        Copy-Item $EnvExampleFile $EnvFile
        Write-Host "已创建 .env 文件，请根据需要编辑配置"
    } else {
        Write-Warning ".env.example 文件不存在"
    }
}

# 创建 uploads 目录
$UploadsDir = Join-Path $AppDir "uploads"
if (-not (Test-Path $UploadsDir)) {
    New-Item -ItemType Directory -Path $UploadsDir
    Write-Host "创建 uploads 目录"
}

Write-Host "启动应用..."
# 使用 gunicorn 运行应用 (Windows 上可能需要使用 gunicorn[gevent] 或其他 worker)
$env:PYTHONPATH = $AppDir
Start-Process -FilePath "gunicorn" -ArgumentList @("app.main:app", "-c", "gunicorn_conf.py", "--bind", "0.0.0.0:8000")