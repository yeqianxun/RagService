
import httpx
import sys

BASE_URL = "http://localhost:8000"

def print_separator(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def test_health():
    print_separator("健康检查接口")
    try:
        response = httpx.get(f"{BASE_URL}/api/v1/health", timeout=5)
        if response.status_code == 200:
            print(f"✅ 成功！响应: {response.json()}")
            return True
        else:
            print(f"❌ 失败！状态码: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 无法连接: {str(e)}")
        print("\n💡 请确保应用正在运行！")
        print("   在另一个终端运行: python -m uvicorn app.main:app --reload")
        return False

def test_api_docs():
    print_separator("API 文档页面")
    try:
        response = httpx.get(f"{BASE_URL}/docs", timeout=5)
        if response.status_code == 200:
            print("✅ 成功！API 文档页面可访问")
            print(f"   在浏览器打开: {BASE_URL}/docs")
            return True
        else:
            print(f"❌ 失败！状态码: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 无法连接: {str(e)}")
        return False

def test_metrics():
    print_separator("Prometheus 指标接口")
    try:
        response = httpx.get(f"{BASE_URL}/metrics", timeout=5)
        if response.status_code == 200:
            print(f"✅ 成功！指标页面可访问，数据长度: {len(response.text)}")
            return True
        else:
            print(f"❌ 失败！状态码: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 无法连接: {str(e)}")
        return False

def main():
    print("=" * 60)
    print("🚀 FastAPI RAG 系统 - 快速测试")
    print("=" * 60)
    print(f"测试地址: {BASE_URL}")
    
    results = []
    results.append(("健康检查", test_health()))
    results.append(("API 文档", test_api_docs()))
    results.append(("Prometheus 指标", test_metrics()))
    
    print_separator("测试总结")
    success_count = sum(1 for _, ok in results if ok)
    total_count = len(results)
    
    for name, ok in results:
        status = "✅" if ok else "❌"
        print(f"  {status} {name}")
    
    print(f"\n📊 总计: {success_count}/{total_count} 个接口正常")
    
    if success_count == total_count:
        print("\n🎉 所有接口测试通过！系统运行正常！")
    else:
        print("\n⚠️ 部分接口异常，建议检查")
    return 0 if success_count == total_count else 1

if __name__ == "__main__":
    sys.exit(main())

