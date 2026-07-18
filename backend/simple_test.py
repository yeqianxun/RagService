
import urllib.request
import json
import sys

BASE_URL = "http://localhost:8000"

def print_separator(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def test_url(path, description):
    try:
        url = f"{BASE_URL}{path}"
        with urllib.request.urlopen(url, timeout=5) as response:
            data = response.read().decode("utf-8")
            print(f"✅ {description}: 成功")
            if len(data) > 500:
                data = data[:500] + "..."
            print(f"   响应: {data[:100]}...")
            return True
    except Exception as e:
        print(f"❌ {description}: 失败 - {str(e)}")
        return False

def main():
    print_separator("🚀 FastAPI RAG 系统 - 接口测试")
    print(f"测试地址: {BASE_URL}")
    
    results = []
    
    results.append(("健康检查", test_url("/api/v1/health", "健康检查接口")))
    results.append(("API 文档", test_url("/docs", "API 文档页面")))
    results.append(("Prometheus 指标", test_url("/metrics", "Prometheus 指标接口")))
    
    print_separator("📊 测试总结")
    
    success_count = sum(1 for _, ok in results if ok)
    total_count = len(results)
    
    for name, ok in results:
        status = "✅" if ok else "❌"
        print(f"  {status} {name}")
    
    print(f"\n📈 总计: {success_count}/{total_count} 个接口正常")
    
    if success_count == total_count:
        print("\n🎉 所有接口测试通过！系统运行正常！")
        print("\n💡 下一步建议:")
        print("   1. 在浏览器打开: http://localhost:8000/docs")
        print("   2. 在 Swagger UI 中可以测试所有接口")
        print("   3. 默认登录账号: admin@example.com / Admin@123456")
        return 0
    else:
        print("\n⚠️ 部分接口异常，建议检查")
        return 1

if __name__ == "__main__":
    sys.exit(main())

